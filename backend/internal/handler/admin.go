package handler

import (
	"database/sql"
	"encoding/json"
	"time"

	"github.com/gofiber/fiber/v2"
	"gw1/backend/internal/middleware"
)

type AdminHandler struct {
	db *sql.DB
}

func NewAdminHandler(db *sql.DB) *AdminHandler {
	return &AdminHandler{db: db}
}

func (h *AdminHandler) ArchiveStats(c *fiber.Ctx) error {
	var total, archived int
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks`).Scan(&total)
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks WHERE is_archived = true`).Scan(&archived)

	var oldDone int
	h.db.QueryRow(`
		SELECT COUNT(*) FROM tasks
		WHERE status = 'done' AND is_archived = false
		AND completed_at < NOW() - INTERVAL '365 days'`).Scan(&oldDone)

	return c.JSON(fiber.Map{
		"total_tasks":         total,
		"archived_tasks":      archived,
		"archivable_tasks":    oldDone,
	})
}

func (h *AdminHandler) MigrateReview(c *fiber.Ctx) error {
	res, err := h.db.Exec(`UPDATE tasks SET status = 'done', completed_at = NOW() WHERE status = 'in_progress'`)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	return c.JSON(fiber.Map{"migrated": n})
}

func (h *AdminHandler) ArchiveOld(c *fiber.Ctx) error {
	res, err := h.db.Exec(`
		UPDATE tasks SET is_archived = true, archived_at = NOW()
		WHERE status = 'done' AND is_archived = false
		AND completed_at < NOW() - INTERVAL '365 days'`)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	return c.JSON(fiber.Map{"archived": n})
}

type backup struct {
	ExportedAt  time.Time        `json:"exported_at"`
	Users       []map[string]interface{} `json:"users"`
	Departments []map[string]interface{} `json:"departments"`
	Tasks       []map[string]interface{} `json:"tasks"`
	TimeLogs    []map[string]interface{} `json:"time_logs"`
	Rhythms     []map[string]interface{} `json:"rhythms"`
	Plans       []map[string]interface{} `json:"plans"`
}

func (h *AdminHandler) Export(c *fiber.Ctx) error {
	b := backup{ExportedAt: time.Now()}

	b.Users = h.dumpTable(`SELECT id, username, email, full_name, role, is_active, created_at FROM users`)
	b.Departments = h.dumpTable(`SELECT id, name, is_active FROM departments`)
	b.Tasks = h.dumpTable(`
		SELECT id, title, description, status, urgency, task_type, tags::text, dynamic_fields::text,
		       customer_name, customer_phone, customer_email, deadline, created_at, completed_at,
		       department_id, created_by_id, assigned_to_id, parent_task_id, is_archived, archived_at
		FROM tasks ORDER BY id`)
	b.TimeLogs = h.dumpTable(`SELECT id, task_id, user_id, started_at, ended_at FROM time_logs ORDER BY id`)
	b.Rhythms = h.dumpTable(`SELECT id, name, description, frequency, task_title, is_active, created_at FROM rhythms`)
	b.Plans = h.dumpTable(`SELECT id, title, description, release_date, is_converted, created_at FROM plans`)

	c.Set("Content-Disposition", `attachment; filename="backup.json"`)
	c.Set("Content-Type", "application/json")
	data, _ := json.MarshalIndent(b, "", "  ")
	return c.Send(data)
}

func (h *AdminHandler) dumpTable(q string) []map[string]interface{} {
	rows, err := h.db.Query(q)
	if err != nil {
		return nil
	}
	defer rows.Close()

	cols, _ := rows.Columns()
	var result []map[string]interface{}
	for rows.Next() {
		vals := make([]interface{}, len(cols))
		ptrs := make([]interface{}, len(cols))
		for i := range vals {
			ptrs[i] = &vals[i]
		}
		rows.Scan(ptrs...)
		row := map[string]interface{}{}
		for i, col := range cols {
			row[col] = vals[i]
		}
		result = append(result, row)
	}
	return result
}

func (h *AdminHandler) Preview(c *fiber.Ctx) error {
	var total int
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks`).Scan(&total)
	var users int
	h.db.QueryRow(`SELECT COUNT(*) FROM users`).Scan(&users)
	return c.JSON(fiber.Map{"tasks": total, "users": users})
}

// Import restores from a JSON backup — super_admin only.
func (h *AdminHandler) Import(c *fiber.Ctx) error {
	claims := middleware.GetClaims(c)
	if !claims.Role.IsSuperAdmin() {
		return fiber.ErrForbidden
	}

	var b backup
	if err := c.BodyParser(&b); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "invalid backup JSON")
	}

	// This is a destructive operation — only allowed explicitly.
	// In a real system you'd wrap this in a transaction.
	return c.JSON(fiber.Map{
		"message": "import endpoint stub — implement with full transaction if needed",
		"users":   len(b.Users),
		"tasks":   len(b.Tasks),
	})
}
