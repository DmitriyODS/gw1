package handler

import (
	"strconv"
	"time"

	"github.com/gofiber/fiber/v2"
	"gw1/backend/internal/domain"
	"gw1/backend/internal/middleware"
	"gw1/backend/internal/repository"
)

type RhythmHandler struct {
	rhythms *repository.RhythmRepo
	tasks   *repository.TaskRepo
}

func NewRhythmHandler(rhythms *repository.RhythmRepo, tasks *repository.TaskRepo) *RhythmHandler {
	return &RhythmHandler{rhythms: rhythms, tasks: tasks}
}

func (h *RhythmHandler) List(c *fiber.Ctx) error {
	rhythms, err := h.rhythms.FindAll()
	if err != nil {
		return err
	}
	return c.JSON(fiber.Map{"data": rhythms})
}

func (h *RhythmHandler) Create(c *fiber.Ctx) error {
	claims := middleware.GetClaims(c)
	inp := &repository.CreateRhythmInput{}
	if err := c.BodyParser(inp); err != nil {
		return fiber.ErrBadRequest
	}
	if inp.Name == "" || inp.TaskTitle == "" {
		return fiber.NewError(fiber.StatusBadRequest, "name and task_title required")
	}
	if inp.TaskUrgency == "" {
		inp.TaskUrgency = domain.UrgencyNormal
	}
	if inp.TaskTags == nil {
		inp.TaskTags = []string{}
	}
	r, err := h.rhythms.Create(inp, claims.UserID)
	if err != nil {
		return err
	}
	return c.Status(fiber.StatusCreated).JSON(r)
}

func (h *RhythmHandler) Update(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	inp := &repository.UpdateRhythmInput{}
	if err := c.BodyParser(inp); err != nil {
		return fiber.ErrBadRequest
	}
	if inp.TaskTags == nil {
		inp.TaskTags = []string{}
	}
	r, err := h.rhythms.Update(id, inp)
	if err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	return c.JSON(r)
}

func (h *RhythmHandler) Delete(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	if err := h.rhythms.Delete(id); err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	return c.JSON(fiber.Map{"ok": true})
}

func (h *RhythmHandler) Toggle(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	var body struct {
		Active bool `json:"active"`
	}
	c.BodyParser(&body)
	if err := h.rhythms.Toggle(id, body.Active); err != nil {
		return err
	}
	r, _ := h.rhythms.FindByID(id)
	return c.JSON(r)
}

func (h *RhythmHandler) Run(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	claims := middleware.GetClaims(c)

	r, err := h.rhythms.FindByID(id)
	if err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}

	task, err := h.tasks.Create(&repository.CreateTaskInput{
		Title:         r.TaskTitle,
		Description:   r.TaskDescription,
		Urgency:       r.TaskUrgency,
		TaskType:      r.TaskType,
		Tags:          r.TaskTags,
		DepartmentID:  r.DepartmentID,
		DynamicFields: map[string]interface{}{},
	}, claims.UserID)
	if err != nil {
		return err
	}

	h.rhythms.UpdateLastRun(id)
	return c.JSON(fiber.Map{"rhythm": r, "created_task": task})
}

// isDue checks if a rhythm should fire today.
func isDue(r *domain.Rhythm) bool {
	now := time.Now()
	switch r.Frequency {
	case domain.FrequencyDaily:
		return true
	case domain.FrequencyWeekly:
		if r.DayOfWeek == nil {
			return false
		}
		return int(now.Weekday()) == *r.DayOfWeek
	case domain.FrequencyMonthly:
		if r.DayOfMonth == nil {
			return false
		}
		return now.Day() == *r.DayOfMonth
	}
	return false
}
