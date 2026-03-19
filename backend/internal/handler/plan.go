package handler

import (
	"strconv"

	"github.com/gofiber/fiber/v2"
	"gw1/backend/internal/domain"
	"gw1/backend/internal/middleware"
	"gw1/backend/internal/repository"
)


type PlanHandler struct {
	plans *repository.PlanRepo
	tasks *repository.TaskRepo
}

func NewPlanHandler(plans *repository.PlanRepo, tasks *repository.TaskRepo) *PlanHandler {
	return &PlanHandler{plans: plans, tasks: tasks}
}

func (h *PlanHandler) List(c *fiber.Ctx) error {
	claims := middleware.GetClaims(c)

	// Auto-convert any due plans before returning the list
	autoConverted := 0
	due, err := h.plans.FindDue()
	if err == nil {
		for _, p := range due {
			task, err := h.tasks.Create(&repository.CreateTaskInput{
				Title:         p.Title,
				Description:   p.Description,
				Urgency:       p.Urgency,
				TaskType:      p.TaskType,
				Tags:          p.Tags,
				DynamicFields: p.DynamicFields,
				CustomerName:  p.CustomerName,
				CustomerPhone: p.CustomerPhone,
				CustomerEmail: p.CustomerEmail,
				DepartmentID:  p.DepartmentID,
			}, claims.UserID)
			if err == nil {
				h.plans.MarkConverted(p.ID, task.ID)
				autoConverted++
			}
		}
	}

	plans, err := h.plans.FindAll()
	if err != nil {
		return err
	}
	groups, _ := h.plans.FindGroups()
	return c.JSON(fiber.Map{"data": plans, "groups": groups, "auto_converted": autoConverted})
}

func (h *PlanHandler) Create(c *fiber.Ctx) error {
	claims := middleware.GetClaims(c)
	inp := &repository.CreatePlanInput{}
	if err := c.BodyParser(inp); err != nil {
		return fiber.ErrBadRequest
	}
	if inp.Title == "" {
		return fiber.NewError(fiber.StatusBadRequest, "title required")
	}
	if inp.Urgency == "" {
		inp.Urgency = domain.UrgencyNormal
	}
	if inp.Tags == nil {
		inp.Tags = []string{}
	}
	p, err := h.plans.Create(inp, claims.UserID)
	if err != nil {
		return err
	}
	return c.Status(fiber.StatusCreated).JSON(p)
}

func (h *PlanHandler) Update(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	inp := &repository.UpdatePlanInput{}
	if err := c.BodyParser(inp); err != nil {
		return fiber.ErrBadRequest
	}
	if inp.Tags == nil {
		inp.Tags = []string{}
	}
	p, err := h.plans.Update(id, inp)
	if err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	return c.JSON(p)
}

func (h *PlanHandler) Delete(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	if err := h.plans.Delete(id); err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	return c.JSON(fiber.Map{"ok": true})
}

// Push converts a plan to a task immediately.
func (h *PlanHandler) Push(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	claims := middleware.GetClaims(c)

	plan, err := h.plans.FindByID(id)
	if err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	if plan.IsConverted {
		return fiber.NewError(fiber.StatusConflict, "already converted")
	}

	task, err := h.tasks.Create(&repository.CreateTaskInput{
		Title:         plan.Title,
		Description:   plan.Description,
		Urgency:       plan.Urgency,
		TaskType:      plan.TaskType,
		Tags:          plan.Tags,
		DynamicFields: plan.DynamicFields,
		CustomerName:  plan.CustomerName,
		CustomerPhone: plan.CustomerPhone,
		CustomerEmail: plan.CustomerEmail,
		DepartmentID:  plan.DepartmentID,
	}, claims.UserID)
	if err != nil {
		return err
	}

	h.plans.MarkConverted(id, task.ID)
	plan, _ = h.plans.FindByID(id)
	return c.JSON(fiber.Map{"plan": plan, "created_task": task})
}

// ConvertDue auto-converts all due plans (called on list or separately).
func (h *PlanHandler) ConvertDue(c *fiber.Ctx) error {
	claims := middleware.GetClaims(c)
	due, err := h.plans.FindDue()
	if err != nil {
		return err
	}
	converted := 0
	for _, p := range due {
		task, err := h.tasks.Create(&repository.CreateTaskInput{
			Title:         p.Title,
			Description:   p.Description,
			Urgency:       p.Urgency,
			TaskType:      p.TaskType,
			Tags:          p.Tags,
			DynamicFields: p.DynamicFields,
			CustomerName:  p.CustomerName,
			CustomerPhone: p.CustomerPhone,
			CustomerEmail: p.CustomerEmail,
			DepartmentID:  p.DepartmentID,
		}, claims.UserID)
		if err == nil {
			h.plans.MarkConverted(p.ID, task.ID)
			converted++
		}
	}
	return c.JSON(fiber.Map{"converted": converted})
}

// -- Group endpoints --

func (h *PlanHandler) ListGroups(c *fiber.Ctx) error {
	groups, err := h.plans.FindGroups()
	if err != nil {
		return err
	}
	return c.JSON(fiber.Map{"data": groups})
}

func (h *PlanHandler) CreateGroup(c *fiber.Ctx) error {
	claims := middleware.GetClaims(c)
	var body struct {
		Name string `json:"name"`
	}
	if err := c.BodyParser(&body); err != nil || body.Name == "" {
		return fiber.NewError(fiber.StatusBadRequest, "name required")
	}
	g, err := h.plans.CreateGroup(body.Name, claims.UserID)
	if err != nil {
		return err
	}
	return c.Status(fiber.StatusCreated).JSON(g)
}

func (h *PlanHandler) DeleteGroup(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	if err := h.plans.DeleteGroup(id); err != nil {
		return err
	}
	return c.JSON(fiber.Map{"ok": true})
}
