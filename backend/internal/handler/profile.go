package handler

import (
	"database/sql"
	"fmt"
	"math/rand"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
	"golang.org/x/crypto/bcrypt"
	"gw1/backend/internal/middleware"
	"gw1/backend/internal/repository"
)

type ProfileHandler struct {
	users     *repository.UserRepo
	db        *sql.DB
	avatarDir string
}

func NewProfileHandler(users *repository.UserRepo, db *sql.DB, avatarDir string) *ProfileHandler {
	return &ProfileHandler{users: users, db: db, avatarDir: avatarDir}
}

func (h *ProfileHandler) Get(c *fiber.Ctx) error {
	claims := middleware.GetClaims(c)
	user, err := h.users.FindByID(claims.UserID)
	if err != nil {
		return err
	}

	now := time.Now()
	weekStart := now.AddDate(0, 0, -7)
	monthStart := now.AddDate(0, -1, 0)

	// Time stats
	var totalSec, weekSec, monthSec int64
	h.db.QueryRow(`SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, NOW()) - started_at))::bigint), 0) FROM time_logs WHERE user_id = $1`, claims.UserID).Scan(&totalSec)
	h.db.QueryRow(`SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, NOW()) - started_at))::bigint), 0) FROM time_logs WHERE user_id = $1 AND started_at >= $2`, claims.UserID, weekStart).Scan(&weekSec)
	h.db.QueryRow(`SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, NOW()) - started_at))::bigint), 0) FROM time_logs WHERE user_id = $1 AND started_at >= $2`, claims.UserID, monthStart).Scan(&monthSec)

	// Tasks stats
	var createdCount, completedCount int
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks WHERE created_by_id = $1`, claims.UserID).Scan(&createdCount)
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks WHERE assigned_to_id = $1 AND status = 'done'`, claims.UserID).Scan(&completedCount)

	// Recent tasks worked on (5 latest via time_logs)
	recentRows, _ := h.db.Query(`
		SELECT DISTINCT ON (t.id) t.id, t.title, t.status, t.urgency, MAX(tl.started_at) as last_work
		FROM time_logs tl
		JOIN tasks t ON t.id = tl.task_id
		WHERE tl.user_id = $1
		GROUP BY t.id, t.title, t.status, t.urgency
		ORDER BY t.id, last_work DESC
		LIMIT 5`, claims.UserID)
	recentTasks := []fiber.Map{}
	if recentRows != nil {
		defer recentRows.Close()
		for recentRows.Next() {
			var id int
			var title, status, urgency string
			var lastWork time.Time
			recentRows.Scan(&id, &title, &status, &urgency, &lastWork)
			recentTasks = append(recentTasks, fiber.Map{
				"id": id, "title": title, "status": status, "urgency": urgency, "last_work": lastWork,
			})
		}
	}

	return c.JSON(fiber.Map{
		"user":            user,
		"total_seconds":   totalSec,
		"week_seconds":    weekSec,
		"month_seconds":   monthSec,
		"created_tasks":   createdCount,
		"completed_tasks": completedCount,
		"recent_tasks":    recentTasks,
	})
}

func (h *ProfileHandler) Update(c *fiber.Ctx) error {
	claims := middleware.GetClaims(c)
	var body struct {
		FullName    *string `json:"full_name"`
		Email       *string `json:"email"`
		OldPassword string  `json:"old_password"`
		NewPassword string  `json:"new_password"`
	}
	if err := c.BodyParser(&body); err != nil {
		return fiber.ErrBadRequest
	}

	// Password change
	if body.NewPassword != "" {
		_, hash, err := h.users.FindByUsername("")
		// re-fetch by ID
		_ = hash
		_ = err
		var currentHash string
		h.db.QueryRow(`SELECT password_hash FROM users WHERE id = $1`, claims.UserID).Scan(&currentHash)
		if err := bcrypt.CompareHashAndPassword([]byte(currentHash), []byte(body.OldPassword)); err != nil {
			return fiber.NewError(fiber.StatusBadRequest, "wrong current password")
		}
		newHash, _ := bcrypt.GenerateFromPassword([]byte(body.NewPassword), bcrypt.DefaultCost)
		h.users.UpdatePassword(claims.UserID, string(newHash))
	}

	user, err := h.users.Update(claims.UserID, &repository.UpdateUserInput{
		FullName: body.FullName,
		Email:    body.Email,
	})
	if err != nil {
		return err
	}
	return c.JSON(user)
}

func (h *ProfileHandler) UploadAvatar(c *fiber.Ctx) error {
	claims := middleware.GetClaims(c)

	if c.FormValue("reset") == "true" {
		// Remove existing avatar
		if err := os.MkdirAll(h.avatarDir, 0755); err == nil {
			files, _ := filepath.Glob(filepath.Join(h.avatarDir, fmt.Sprintf("%d_*", claims.UserID)))
			for _, f := range files {
				os.Remove(f)
			}
		}
		h.users.Update(claims.UserID, &repository.UpdateUserInput{AvatarPath: strPtr("")})
		return c.JSON(fiber.Map{"ok": true})
	}

	file, err := c.FormFile("avatar")
	if err != nil {
		return fiber.ErrBadRequest
	}

	ext := filepath.Ext(file.Filename)
	stored := fmt.Sprintf("%d_%s%s", claims.UserID, uuid.New().String(), ext)
	dst := filepath.Join(h.avatarDir, stored)

	if err := os.MkdirAll(h.avatarDir, 0755); err != nil {
		return err
	}
	if err := c.SaveFile(file, dst); err != nil {
		return err
	}

	user, err := h.users.Update(claims.UserID, &repository.UpdateUserInput{AvatarPath: &stored})
	if err != nil {
		return err
	}
	return c.JSON(user)
}

func (h *ProfileHandler) GetAvatar(c *fiber.Ctx) error {
	userID, _ := strconv.Atoi(c.Params("user_id"))

	user, err := h.users.FindByID(userID)
	if err != nil {
		return fiber.ErrNotFound
	}

	if user.AvatarPath != nil && *user.AvatarPath != "" {
		path := filepath.Join(h.avatarDir, *user.AvatarPath)
		if _, err := os.Stat(path); err == nil {
			return c.SendFile(path)
		}
	}

	// Generate procedural pixel-art SVG
	svg := generateAvatarSVG(userID)
	c.Set("Content-Type", "image/svg+xml")
	c.Set("Cache-Control", "public, max-age=86400")
	return c.SendString(svg)
}

func generateAvatarSVG(seed int) string {
	r := rand.New(rand.NewSource(int64(seed)))
	size := 8
	colors := []string{
		"#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
		"#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F",
	}
	bg := colors[r.Intn(len(colors))]
	fg := colors[r.Intn(len(colors))]

	pixels := make([][]bool, size)
	for i := range pixels {
		pixels[i] = make([]bool, size)
		for j := 0; j < size/2; j++ {
			pixels[i][j] = r.Intn(2) == 1
			pixels[i][size-1-j] = pixels[i][j] // mirror
		}
	}

	cellSize := 40
	total := size * cellSize
	svg := fmt.Sprintf(`<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">`, total, total)
	svg += fmt.Sprintf(`<rect width="%d" height="%d" fill="%s"/>`, total, total, bg)
	for i, row := range pixels {
		for j, filled := range row {
			if filled {
				svg += fmt.Sprintf(`<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>`,
					j*cellSize, i*cellSize, cellSize, cellSize, fg)
			}
		}
	}
	svg += `</svg>`
	return svg
}

func strPtr(s string) *string { return &s }
