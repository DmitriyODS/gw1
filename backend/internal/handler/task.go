package handler

import (
	"archive/zip"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
	"gw1/backend/internal/domain"
	"gw1/backend/internal/middleware"
	"gw1/backend/internal/repository"
)

type TaskHandler struct {
	tasks    *repository.TaskRepo
	timelogs *repository.TimeLogRepo
	uploadDir string
}

func NewTaskHandler(tasks *repository.TaskRepo, tl *repository.TimeLogRepo, uploadDir string) *TaskHandler {
	return &TaskHandler{tasks: tasks, timelogs: tl, uploadDir: uploadDir}
}

func (h *TaskHandler) List(c *fiber.Ctx) error {
	f := repository.TaskFilter{
		Page:    c.QueryInt("page", 1),
		PerPage: c.QueryInt("per_page", 50),
	}
	if s := c.Query("status"); s != "" {
		st := domain.TaskStatus(s)
		f.Status = &st
	}
	if u := c.Query("urgency"); u != "" {
		ur := domain.Urgency(u)
		f.Urgency = &ur
	}
	if d := c.QueryInt("department_id", 0); d != 0 {
		f.DepartmentID = &d
	}
	if a := c.QueryInt("assigned_to_id", 0); a != 0 {
		f.AssignedToID = &a
	}
	if c.Query("archived") == "true" {
		t := true
		f.Archived = &t
	}
	f.ParentOnly = c.QueryBool("parent_only", false)
	f.Free = c.QueryBool("free", false)

	// Tags: comma-separated or repeated params
	if tags := c.Query("tags"); tags != "" {
		for _, t := range strings.Split(tags, ",") {
			if t = strings.TrimSpace(t); t != "" {
				f.Tags = append(f.Tags, t)
			}
		}
	}

	tasks, total, err := h.tasks.FindAll(f)
	if err != nil {
		return err
	}
	return c.JSON(fiber.Map{"data": tasks, "total": total})
}

func (h *TaskHandler) Get(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	task, err := h.tasks.FindByID(id)
	if err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	if err != nil {
		return err
	}

	// enrich with subtasks, attachments, comments, timelogs
	task.Subtasks, _ = h.tasks.FindSubtasks(task.ID)
	task.Attachments, _ = h.tasks.FindAttachments(task.ID)
	task.Comments, _ = h.tasks.FindComments(task.ID)
	task.TimeLogs, _ = h.timelogs.FindByTask(task.ID)

	return c.JSON(task)
}

func (h *TaskHandler) Create(c *fiber.Ctx) error {
	claims := middleware.GetClaims(c)
	var body struct {
		Title         string                 `json:"title"`
		Description   string                 `json:"description"`
		Urgency       domain.Urgency         `json:"urgency"`
		TaskType      *string                `json:"task_type"`
		Tags          []string               `json:"tags"`
		DynamicFields map[string]interface{} `json:"dynamic_fields"`
		CustomerName  *string                `json:"customer_name"`
		CustomerPhone *string                `json:"customer_phone"`
		CustomerEmail *string                `json:"customer_email"`
		Deadline      *time.Time             `json:"deadline"`
		DepartmentID  *int                   `json:"department_id"`
		AssignedToID  *int                   `json:"assigned_to_id"`
		ParentTaskID  *int                   `json:"parent_task_id"`
	}
	if err := c.BodyParser(&body); err != nil {
		return fiber.ErrBadRequest
	}
	if body.Title == "" {
		return fiber.NewError(fiber.StatusBadRequest, "title required")
	}
	if body.Urgency == "" {
		body.Urgency = domain.UrgencyNormal
	}
	if body.Tags == nil {
		body.Tags = []string{}
	}

	inp := &repository.CreateTaskInput{
		Title:         body.Title,
		Description:   body.Description,
		Urgency:       body.Urgency,
		TaskType:      body.TaskType,
		Tags:          body.Tags,
		DynamicFields: body.DynamicFields,
		CustomerName:  body.CustomerName,
		CustomerPhone: body.CustomerPhone,
		CustomerEmail: body.CustomerEmail,
		Deadline:      body.Deadline,
		DepartmentID:  body.DepartmentID,
		AssignedToID:  body.AssignedToID,
		ParentTaskID:  body.ParentTaskID,
	}
	task, err := h.tasks.Create(inp, claims.UserID)
	if err != nil {
		return err
	}

	// Auto-create subtasks for publication type
	if body.TaskType != nil && *body.TaskType == "publication" {
		designType := "design"
		textType := "text"
		h.tasks.Create(&repository.CreateTaskInput{
			Title: fmt.Sprintf("[Дизайн] %s", body.Title),
			Urgency: body.Urgency, TaskType: &designType,
			DepartmentID: body.DepartmentID, ParentTaskID: &task.ID,
			Tags: []string{"design"}, DynamicFields: map[string]interface{}{},
		}, claims.UserID)
		h.tasks.Create(&repository.CreateTaskInput{
			Title: fmt.Sprintf("[Текст] %s", body.Title),
			Urgency: body.Urgency, TaskType: &textType,
			DepartmentID: body.DepartmentID, ParentTaskID: &task.ID,
			Tags: []string{"text"}, DynamicFields: map[string]interface{}{},
		}, claims.UserID)
	}

	return c.Status(fiber.StatusCreated).JSON(task)
}

func (h *TaskHandler) Update(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	var body struct {
		Title         *string                `json:"title"`
		Description   *string                `json:"description"`
		Urgency       *domain.Urgency        `json:"urgency"`
		TaskType      *string                `json:"task_type"`
		Tags          []string               `json:"tags"`
		DynamicFields map[string]interface{} `json:"dynamic_fields"`
		CustomerName  *string                `json:"customer_name"`
		CustomerPhone *string                `json:"customer_phone"`
		CustomerEmail *string                `json:"customer_email"`
		Deadline      *time.Time             `json:"deadline"`
		DepartmentID  *int                   `json:"department_id"`
		AssignedToID  *int                   `json:"assigned_to_id"`
	}
	if err := c.BodyParser(&body); err != nil {
		return fiber.ErrBadRequest
	}
	task, err := h.tasks.Update(id, &repository.UpdateTaskInput{
		Title: body.Title, Description: body.Description,
		Urgency: body.Urgency, TaskType: body.TaskType,
		Tags: body.Tags, DynamicFields: body.DynamicFields,
		CustomerName: body.CustomerName, CustomerPhone: body.CustomerPhone,
		CustomerEmail: body.CustomerEmail, Deadline: body.Deadline,
		DepartmentID: body.DepartmentID, AssignedToID: body.AssignedToID,
	})
	if err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	return c.JSON(task)
}

func (h *TaskHandler) Delete(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	if err := h.tasks.Delete(id); err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	return c.JSON(fiber.Map{"ok": true})
}

func (h *TaskHandler) Move(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	var body struct {
		Status domain.TaskStatus `json:"status"`
	}
	if err := c.BodyParser(&body); err != nil {
		return fiber.ErrBadRequest
	}
	if err := h.tasks.UpdateStatus(id, body.Status); err != nil {
		return err
	}
	task, _ := h.tasks.FindByID(id)
	return c.JSON(task)
}

func (h *TaskHandler) TimerStart(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	claims := middleware.GetClaims(c)

	task, err := h.tasks.FindByID(id)
	if err != nil {
		return fiber.ErrNotFound
	}
	if task.AssignedToID != nil && *task.AssignedToID != claims.UserID {
		return fiber.NewError(fiber.StatusConflict, "task already taken")
	}

	// Check user has no active timer
	active, _ := h.timelogs.FindActive(claims.UserID)
	if active != nil {
		return fiber.NewError(fiber.StatusConflict, "you already have an active timer")
	}

	// Assign if not assigned
	if task.AssignedToID == nil {
		h.tasks.SetAssigned(id, &claims.UserID)
	}
	h.tasks.UpdateStatus(id, domain.StatusInProgress)
	h.timelogs.Start(id, claims.UserID)

	task, _ = h.tasks.FindByID(id)
	return c.JSON(task)
}

func (h *TaskHandler) TimerForceStart(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	claims := middleware.GetClaims(c)

	// Pause any active timer
	active, _ := h.timelogs.FindActive(claims.UserID)
	if active != nil {
		h.timelogs.Stop(active.ID)
		h.tasks.UpdateStatus(active.TaskID, domain.StatusPaused)
	}

	task, err := h.tasks.FindByID(id)
	if err != nil {
		return fiber.ErrNotFound
	}
	if task.AssignedToID == nil {
		h.tasks.SetAssigned(id, &claims.UserID)
	}
	h.tasks.UpdateStatus(id, domain.StatusInProgress)
	h.timelogs.Start(id, claims.UserID)

	task, _ = h.tasks.FindByID(id)
	return c.JSON(task)
}

func (h *TaskHandler) TimerPause(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	claims := middleware.GetClaims(c)

	active, _ := h.timelogs.FindActive(claims.UserID)
	if active != nil && active.TaskID == id {
		h.timelogs.Stop(active.ID)
	}
	h.tasks.UpdateStatus(id, domain.StatusPaused)

	task, _ := h.tasks.FindByID(id)
	return c.JSON(task)
}

func (h *TaskHandler) Done(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	claims := middleware.GetClaims(c)

	// Block if there are open subtasks
	subtasks, _ := h.tasks.FindSubtasks(id)
	for _, st := range subtasks {
		if st.Status != domain.StatusDone {
			return fiber.NewError(fiber.StatusConflict, "has_open_subtasks")
		}
	}

	// Stop timer if running
	active, _ := h.timelogs.FindActive(claims.UserID)
	if active != nil && active.TaskID == id {
		h.timelogs.Stop(active.ID)
	}
	h.tasks.MarkDone(id)

	task, _ := h.tasks.FindByID(id)
	return c.JSON(task)
}

func (h *TaskHandler) Delegate(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	var body struct {
		UserID int `json:"user_id"`
	}
	if err := c.BodyParser(&body); err != nil {
		return fiber.ErrBadRequest
	}
	h.tasks.SetAssigned(id, &body.UserID)
	task, _ := h.tasks.FindByID(id)
	return c.JSON(task)
}

func (h *TaskHandler) Unassign(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	h.tasks.SetAssigned(id, nil)
	task, _ := h.tasks.FindByID(id)
	return c.JSON(task)
}

func (h *TaskHandler) MyTimer(c *fiber.Ctx) error {
	claims := middleware.GetClaims(c)
	active, err := h.timelogs.FindActive(claims.UserID)
	if err != nil {
		return err
	}
	if active == nil {
		return c.JSON(fiber.Map{"active": nil})
	}
	task, _ := h.tasks.FindByID(active.TaskID)
	return c.JSON(fiber.Map{
		"active":     active,
		"task":       task,
		"elapsed_sec": int(time.Since(active.StartedAt).Seconds()),
	})
}

// UploadAttachment handles multipart file upload.
func (h *TaskHandler) UploadAttachment(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	file, err := c.FormFile("file")
	if err != nil {
		return fiber.ErrBadRequest
	}

	ext := filepath.Ext(file.Filename)
	stored := uuid.New().String() + ext
	dst := filepath.Join(h.uploadDir, stored)
	if err := c.SaveFile(file, dst); err != nil {
		return err
	}

	att, err := h.tasks.CreateAttachment(id, stored, file.Filename)
	if err != nil {
		os.Remove(dst)
		return err
	}
	return c.Status(fiber.StatusCreated).JSON(att)
}

func (h *TaskHandler) DeleteAttachment(c *fiber.Ctx) error {
	attID, _ := strconv.Atoi(c.Params("att_id"))
	att, err := h.tasks.FindAttachmentByID(attID)
	if err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	os.Remove(filepath.Join(h.uploadDir, att.Filename))
	h.tasks.DeleteAttachment(attID)
	return c.JSON(fiber.Map{"ok": true})
}

func (h *TaskHandler) DownloadZip(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	atts, err := h.tasks.FindAttachments(id)
	if err != nil {
		return err
	}

	c.Set("Content-Disposition", fmt.Sprintf(`attachment; filename="task_%d_files.zip"`, id))
	c.Set("Content-Type", "application/zip")

	w := zip.NewWriter(c.Response().BodyWriter())
	defer w.Close()

	for _, att := range atts {
		f, err := os.Open(filepath.Join(h.uploadDir, att.Filename))
		if err != nil {
			continue
		}
		zf, _ := w.Create(att.OriginalName)
		io.Copy(zf, f)
		f.Close()
	}
	return nil
}

func (h *TaskHandler) AddComment(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	claims := middleware.GetClaims(c)

	var filename, originalName *string

	// Check for attached file
	file, err := c.FormFile("file")
	if err == nil {
		ext := filepath.Ext(file.Filename)
		stored := uuid.New().String() + ext
		dst := filepath.Join(h.uploadDir, stored)
		if err := c.SaveFile(file, dst); err == nil {
			filename = &stored
			originalName = &file.Filename
		}
	}

	text := c.FormValue("text")
	comment, err := h.tasks.CreateComment(id, claims.UserID, text, filename, originalName)
	if err != nil {
		return err
	}
	return c.Status(fiber.StatusCreated).JSON(comment)
}

func (h *TaskHandler) DeleteComment(c *fiber.Ctx) error {
	commentID, _ := strconv.Atoi(c.Params("comment_id"))
	claims := middleware.GetClaims(c)

	comment, err := h.tasks.FindCommentByID(commentID)
	if err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	// Only author or manager+ can delete
	if comment.UserID != claims.UserID && !claims.Role.CanManage() {
		return fiber.ErrForbidden
	}
	if comment.Filename != nil {
		os.Remove(filepath.Join(h.uploadDir, *comment.Filename))
	}
	h.tasks.DeleteComment(commentID)
	return c.JSON(fiber.Map{"ok": true})
}
