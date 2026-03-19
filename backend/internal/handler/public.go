package handler

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
	"gw1/backend/internal/domain"
	"gw1/backend/internal/repository"
)

type PublicHandler struct {
	tasks     *repository.TaskRepo
	depts     *repository.DepartmentRepo
	db        *sql.DB
	uploadDir string
}

func NewPublicHandler(tasks *repository.TaskRepo, depts *repository.DepartmentRepo, db *sql.DB, uploadDir string) *PublicHandler {
	return &PublicHandler{tasks: tasks, depts: depts, db: db, uploadDir: uploadDir}
}

// Submit creates a task from an external (unauthenticated) form.
// Supports both JSON and multipart/form-data (for file attachments).
func (h *PublicHandler) Submit(c *fiber.Ctx) error {
	var (
		title         string
		description   string
		customerName  *string
		customerPhone *string
		customerEmail *string
		departmentID  *int
		taskType      *string
		dynamicFields = map[string]interface{}{}
	)

	ct := string(c.Request().Header.ContentType())
	if len(ct) >= 19 && ct[:19] == "multipart/form-data" {
		title = c.FormValue("title")
		description = c.FormValue("description")
		if v := c.FormValue("customer_name"); v != "" { customerName = &v }
		if v := c.FormValue("customer_phone"); v != "" { customerPhone = &v }
		if v := c.FormValue("customer_email"); v != "" { customerEmail = &v }
		if v := c.FormValue("task_type"); v != "" { taskType = &v }
		if v := c.FormValue("dynamic_fields"); v != "" {
			json.Unmarshal([]byte(v), &dynamicFields)
		}
		if v := c.FormValue("department_id"); v != "" {
			var id int
			fmt.Sscanf(v, "%d", &id)
			departmentID = &id
		}
	} else {
		var body struct {
			Title         string                 `json:"title"`
			Description   string                 `json:"description"`
			CustomerName  *string                `json:"customer_name"`
			CustomerPhone *string                `json:"customer_phone"`
			CustomerEmail *string                `json:"customer_email"`
			DepartmentID  *int                   `json:"department_id"`
			TaskType      *string                `json:"task_type"`
			DynamicFields map[string]interface{} `json:"dynamic_fields"`
		}
		if err := c.BodyParser(&body); err != nil {
			return fiber.ErrBadRequest
		}
		title = body.Title
		description = body.Description
		customerName = body.CustomerName
		customerPhone = body.CustomerPhone
		customerEmail = body.CustomerEmail
		departmentID = body.DepartmentID
		taskType = body.TaskType
		if body.DynamicFields != nil {
			dynamicFields = body.DynamicFields
		}
	}

	if title == "" {
		return fiber.NewError(fiber.StatusBadRequest, "title required")
	}

	var creatorID int
	if err := h.db.QueryRow(`SELECT id FROM users WHERE role = 'super_admin' LIMIT 1`).Scan(&creatorID); err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "no admin user found")
	}

	task, err := h.tasks.Create(&repository.CreateTaskInput{
		Title:         title,
		Description:   description,
		Urgency:       domain.UrgencyNormal,
		TaskType:      taskType,
		Tags:          []string{},
		DynamicFields: dynamicFields,
		CustomerName:  customerName,
		CustomerPhone: customerPhone,
		CustomerEmail: customerEmail,
		DepartmentID:  departmentID,
	}, creatorID)
	if err != nil {
		return err
	}

	// Save any uploaded files (multipart only)
	if form, err := c.MultipartForm(); err == nil && form != nil {
		for _, fhs := range form.File {
			for _, fh := range fhs {
				ext := filepath.Ext(fh.Filename)
				stored := uuid.New().String() + ext
				dst := filepath.Join(h.uploadDir, stored)
				if src, err := fh.Open(); err == nil {
					if out, err := os.Create(dst); err == nil {
						io.Copy(out, src)
						out.Close()
						h.tasks.CreateAttachment(task.ID, stored, fh.Filename)
					}
					src.Close()
				}
			}
		}
	}

	return c.Status(fiber.StatusCreated).JSON(task)
}

// Departments returns active departments for the public form.
func (h *PublicHandler) Departments(c *fiber.Ctx) error {
	depts, err := h.depts.FindAll(true)
	if err != nil {
		return err
	}
	return c.JSON(fiber.Map{"data": depts})
}

// TaskTypes returns the 13 external task types for the public form.
func (h *PublicHandler) TaskTypes(c *fiber.Ctx) error {
	return c.JSON(fiber.Map{"data": domain.ExternalTaskTypes})
}
