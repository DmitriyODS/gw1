package handler

import (
	"database/sql"

	"github.com/gofiber/fiber/v2"
	"gw1/backend/internal/domain"
	"gw1/backend/internal/repository"
)

type PublicHandler struct {
	tasks *repository.TaskRepo
	depts *repository.DepartmentRepo
	db    *sql.DB
}

func NewPublicHandler(tasks *repository.TaskRepo, depts *repository.DepartmentRepo, db *sql.DB) *PublicHandler {
	return &PublicHandler{tasks: tasks, depts: depts, db: db}
}

// Submit creates a task from an external (unauthenticated) form.
// The system user (id=1, super_admin) is used as creator.
func (h *PublicHandler) Submit(c *fiber.Ctx) error {
	var body struct {
		Title         string  `json:"title"`
		Description   string  `json:"description"`
		CustomerName  *string `json:"customer_name"`
		CustomerPhone *string `json:"customer_phone"`
		CustomerEmail *string `json:"customer_email"`
		DepartmentID  *int    `json:"department_id"`
		TaskType      *string `json:"task_type"`
	}
	if err := c.BodyParser(&body); err != nil {
		return fiber.ErrBadRequest
	}
	if body.Title == "" {
		return fiber.NewError(fiber.StatusBadRequest, "title required")
	}

	// Find the super_admin to use as creator
	var creatorID int
	if err := h.db.QueryRow(`SELECT id FROM users WHERE role = 'super_admin' LIMIT 1`).Scan(&creatorID); err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "no admin user found")
	}

	task, err := h.tasks.Create(&repository.CreateTaskInput{
		Title:         body.Title,
		Description:   body.Description,
		Urgency:       domain.UrgencyNormal,
		TaskType:      body.TaskType,
		Tags:          []string{},
		DynamicFields: map[string]interface{}{},
		CustomerName:  body.CustomerName,
		CustomerPhone: body.CustomerPhone,
		CustomerEmail: body.CustomerEmail,
		DepartmentID:  body.DepartmentID,
	}, creatorID)
	if err != nil {
		return err
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

// TaskTypes returns available task types.
func (h *PublicHandler) TaskTypes(c *fiber.Ctx) error {
	types := []string{
		"publication", "design", "text", "photo_video", "internal", "external",
	}
	return c.JSON(fiber.Map{"data": types})
}
