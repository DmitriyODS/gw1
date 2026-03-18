package handler

import (
	"strconv"

	"github.com/gofiber/fiber/v2"
	"gw1/backend/internal/repository"
)

type DepartmentHandler struct {
	depts *repository.DepartmentRepo
}

func NewDepartmentHandler(depts *repository.DepartmentRepo) *DepartmentHandler {
	return &DepartmentHandler{depts: depts}
}

func (h *DepartmentHandler) List(c *fiber.Ctx) error {
	activeOnly := c.QueryBool("active_only", false)
	depts, err := h.depts.FindAll(activeOnly)
	if err != nil {
		return err
	}
	return c.JSON(fiber.Map{"data": depts})
}

func (h *DepartmentHandler) Create(c *fiber.Ctx) error {
	var body struct {
		Name string `json:"name"`
	}
	if err := c.BodyParser(&body); err != nil || body.Name == "" {
		return fiber.NewError(fiber.StatusBadRequest, "name required")
	}
	dept, err := h.depts.Create(body.Name)
	if err != nil {
		return fiber.NewError(fiber.StatusConflict, err.Error())
	}
	return c.Status(fiber.StatusCreated).JSON(dept)
}

func (h *DepartmentHandler) Update(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	var body struct {
		Name     string `json:"name"`
		IsActive *bool  `json:"is_active"`
	}
	if err := c.BodyParser(&body); err != nil {
		return fiber.ErrBadRequest
	}
	dept, err := h.depts.Update(id, body.Name, body.IsActive)
	if err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	return c.JSON(dept)
}

func (h *DepartmentHandler) Delete(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	if err := h.depts.Delete(id); err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	return c.JSON(fiber.Map{"ok": true})
}
