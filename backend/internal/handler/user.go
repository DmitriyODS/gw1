package handler

import (
	"strconv"

	"github.com/gofiber/fiber/v2"
	"golang.org/x/crypto/bcrypt"
	"gw1/backend/internal/domain"
	"gw1/backend/internal/repository"
)

type UserHandler struct {
	users *repository.UserRepo
}

func NewUserHandler(users *repository.UserRepo) *UserHandler {
	return &UserHandler{users: users}
}

func (h *UserHandler) List(c *fiber.Ctx) error {
	activeOnly := c.QueryBool("active_only", false)
	users, err := h.users.FindAll(activeOnly)
	if err != nil {
		return err
	}
	return c.JSON(fiber.Map{"data": users})
}

func (h *UserHandler) Get(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	user, err := h.users.FindByID(id)
	if err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	return c.JSON(user)
}

func (h *UserHandler) Create(c *fiber.Ctx) error {
	var body struct {
		Username string      `json:"username"`
		Email    *string     `json:"email"`
		Password string      `json:"password"`
		FullName string      `json:"full_name"`
		Role     domain.Role `json:"role"`
	}
	if err := c.BodyParser(&body); err != nil {
		return fiber.ErrBadRequest
	}
	if body.Username == "" || body.Password == "" {
		return fiber.NewError(fiber.StatusBadRequest, "username and password required")
	}
	if body.Role == "" {
		body.Role = domain.RoleStaff
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(body.Password), bcrypt.DefaultCost)
	if err != nil {
		return err
	}
	user, err := h.users.Create(&repository.CreateUserInput{
		Username:     body.Username,
		Email:        body.Email,
		PasswordHash: string(hash),
		FullName:     body.FullName,
		Role:         body.Role,
	})
	if err != nil {
		return fiber.NewError(fiber.StatusConflict, err.Error())
	}
	return c.Status(fiber.StatusCreated).JSON(user)
}

func (h *UserHandler) Update(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	var body struct {
		Username *string      `json:"username"`
		Email    *string      `json:"email"`
		FullName *string      `json:"full_name"`
		Role     *domain.Role `json:"role"`
		IsActive *bool        `json:"is_active"`
	}
	if err := c.BodyParser(&body); err != nil {
		return fiber.ErrBadRequest
	}
	user, err := h.users.Update(id, &repository.UpdateUserInput{
		Username: body.Username, Email: body.Email,
		FullName: body.FullName, Role: body.Role, IsActive: body.IsActive,
	})
	if err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	return c.JSON(user)
}

func (h *UserHandler) Delete(c *fiber.Ctx) error {
	id, _ := strconv.Atoi(c.Params("id"))
	if err := h.users.Delete(id); err == repository.ErrNotFound {
		return fiber.ErrNotFound
	}
	return c.JSON(fiber.Map{"ok": true})
}
