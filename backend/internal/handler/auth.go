package handler

import (
	"database/sql"
	"time"

	"github.com/gofiber/fiber/v2"
	"golang.org/x/crypto/bcrypt"
	"gw1/backend/internal/middleware"
	"gw1/backend/internal/repository"
)

type AuthHandler struct {
	users *repository.UserRepo
	db    *sql.DB
	secret string
}

func NewAuthHandler(users *repository.UserRepo, db *sql.DB, secret string) *AuthHandler {
	return &AuthHandler{users: users, db: db, secret: secret}
}

func (h *AuthHandler) Login(c *fiber.Ctx) error {
	var body struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	if err := c.BodyParser(&body); err != nil {
		return fiber.ErrBadRequest
	}

	user, hash, err := h.users.FindByUsername(body.Username)
	if err != nil || !user.IsActive {
		return fiber.NewError(fiber.StatusUnauthorized, "invalid credentials")
	}
	if err := bcrypt.CompareHashAndPassword([]byte(hash), []byte(body.Password)); err != nil {
		return fiber.NewError(fiber.StatusUnauthorized, "invalid credentials")
	}

	access, err := middleware.NewAccessToken(user.ID, user.Role, h.secret)
	if err != nil {
		return err
	}
	refresh, err := middleware.NewRefreshToken(user.ID, user.Role, h.secret)
	if err != nil {
		return err
	}

	// persist refresh token
	h.db.Exec(`
		INSERT INTO refresh_tokens (user_id, token, expires_at)
		VALUES ($1, $2, $3)`,
		user.ID, refresh, time.Now().Add(7*24*time.Hour))

	return c.JSON(fiber.Map{
		"access_token":  access,
		"refresh_token": refresh,
		"user":          user,
	})
}

func (h *AuthHandler) Refresh(c *fiber.Ctx) error {
	var body struct {
		RefreshToken string `json:"refresh_token"`
	}
	if err := c.BodyParser(&body); err != nil {
		return fiber.ErrBadRequest
	}

	// validate token
	claims, err := middleware.ParseToken(body.RefreshToken, h.secret)
	if err != nil {
		return fiber.ErrUnauthorized
	}

	// check it exists in DB
	var id int
	err = h.db.QueryRow(`
		SELECT id FROM refresh_tokens
		WHERE token = $1 AND user_id = $2 AND expires_at > NOW()`,
		body.RefreshToken, claims.UserID).Scan(&id)
	if err != nil {
		return fiber.ErrUnauthorized
	}

	user, err := h.users.FindByID(claims.UserID)
	if err != nil || !user.IsActive {
		return fiber.ErrUnauthorized
	}

	access, err := middleware.NewAccessToken(user.ID, user.Role, h.secret)
	if err != nil {
		return err
	}

	return c.JSON(fiber.Map{"access_token": access})
}

func (h *AuthHandler) Logout(c *fiber.Ctx) error {
	var body struct {
		RefreshToken string `json:"refresh_token"`
	}
	c.BodyParser(&body)
	if body.RefreshToken != "" {
		h.db.Exec(`DELETE FROM refresh_tokens WHERE token = $1`, body.RefreshToken)
	}
	return c.JSON(fiber.Map{"ok": true})
}
