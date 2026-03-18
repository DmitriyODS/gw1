package handler

import (
	"database/sql"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/xuri/excelize/v2"
)

type AnalyticsHandler struct {
	db *sql.DB
}

func NewAnalyticsHandler(db *sql.DB) *AnalyticsHandler {
	return &AnalyticsHandler{db: db}
}

// periodStart returns the start of the requested period relative to now.
func periodStart(period string) time.Time {
	now := time.Now()
	switch period {
	case "day":
		return time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())
	case "week":
		return now.AddDate(0, 0, -7)
	case "month":
		return now.AddDate(0, -1, 0)
	case "year":
		return now.AddDate(-1, 0, 0)
	default:
		return now.AddDate(0, -1, 0)
	}
}

func (h *AnalyticsHandler) Dashboard(c *fiber.Ctx) error {
	period := c.Query("period", "month")
	since := periodStart(period)

	// Task counts by status
	statusRows, _ := h.db.Query(`
		SELECT status, COUNT(*) FROM tasks
		WHERE is_archived = false GROUP BY status`)
	byStatus := map[string]int{}
	for statusRows.Next() {
		var s string
		var n int
		statusRows.Scan(&s, &n)
		byStatus[s] = n
	}
	statusRows.Close()

	// Task counts by department
	deptRows, _ := h.db.Query(`
		SELECT COALESCE(d.name, 'Без отдела'), COUNT(t.id)
		FROM tasks t
		LEFT JOIN departments d ON d.id = t.department_id
		WHERE t.is_archived = false
		GROUP BY d.name ORDER BY COUNT(t.id) DESC`)
	byDept := []fiber.Map{}
	for deptRows.Next() {
		var name string
		var n int
		deptRows.Scan(&name, &n)
		byDept = append(byDept, fiber.Map{"name": name, "count": n})
	}
	deptRows.Close()

	// Task counts by type
	typeRows, _ := h.db.Query(`
		SELECT COALESCE(task_type, 'Без типа'), COUNT(*)
		FROM tasks WHERE is_archived = false
		GROUP BY task_type ORDER BY COUNT(*) DESC`)
	byType := []fiber.Map{}
	for typeRows.Next() {
		var name string
		var n int
		typeRows.Scan(&name, &n)
		byType = append(byType, fiber.Map{"name": name, "count": n})
	}
	typeRows.Close()

	// Top performers
	topRows, _ := h.db.Query(`
		SELECT u.id, u.full_name, u.username, COUNT(t.id) as cnt
		FROM users u
		JOIN tasks t ON t.assigned_to_id = u.id
		WHERE t.status = 'done' AND t.completed_at >= $1
		GROUP BY u.id, u.full_name, u.username
		ORDER BY cnt DESC LIMIT 10`, since)
	top := []fiber.Map{}
	for topRows.Next() {
		var id int
		var fullName, username string
		var cnt int
		topRows.Scan(&id, &fullName, &username, &cnt)
		top = append(top, fiber.Map{"id": id, "full_name": fullName, "username": username, "count": cnt})
	}
	topRows.Close()

	// Burnup: created vs done per day over period
	createdRows, _ := h.db.Query(`
		SELECT DATE(created_at), COUNT(*) FROM tasks
		WHERE created_at >= $1 GROUP BY DATE(created_at) ORDER BY DATE(created_at)`, since)
	burnupCreated := []fiber.Map{}
	for createdRows.Next() {
		var d time.Time
		var n int
		createdRows.Scan(&d, &n)
		burnupCreated = append(burnupCreated, fiber.Map{"date": d.Format("2006-01-02"), "count": n})
	}
	createdRows.Close()

	doneRows, _ := h.db.Query(`
		SELECT DATE(completed_at), COUNT(*) FROM tasks
		WHERE completed_at >= $1 GROUP BY DATE(completed_at) ORDER BY DATE(completed_at)`, since)
	burnupDone := []fiber.Map{}
	for doneRows.Next() {
		var d time.Time
		var n int
		doneRows.Scan(&d, &n)
		burnupDone = append(burnupDone, fiber.Map{"date": d.Format("2006-01-02"), "count": n})
	}
	doneRows.Close()

	// Overdue count
	var overdueCount int
	h.db.QueryRow(`
		SELECT COUNT(*) FROM tasks
		WHERE is_archived = false AND status != 'done'
		AND deadline < NOW()`).Scan(&overdueCount)

	return c.JSON(fiber.Map{
		"period":         period,
		"by_status":      byStatus,
		"by_department":  byDept,
		"by_type":        byType,
		"top_performers": top,
		"burnup_created": burnupCreated,
		"burnup_done":    burnupDone,
		"overdue_count":  overdueCount,
	})
}

func (h *AnalyticsHandler) TimeReport(c *fiber.Ctx) error {
	period := c.Query("period", "month")
	since := periodStart(period)

	// Time by user
	userRows, _ := h.db.Query(`
		SELECT u.id, u.full_name, u.username,
		       SUM(EXTRACT(EPOCH FROM (COALESCE(tl.ended_at, NOW()) - tl.started_at)))::bigint as secs
		FROM time_logs tl
		JOIN users u ON u.id = tl.user_id
		WHERE tl.started_at >= $1
		GROUP BY u.id, u.full_name, u.username
		ORDER BY secs DESC`, since)
	byUser := []fiber.Map{}
	for userRows.Next() {
		var id int
		var fullName, username string
		var secs int64
		userRows.Scan(&id, &fullName, &username, &secs)
		byUser = append(byUser, fiber.Map{
			"id": id, "full_name": fullName, "username": username, "seconds": secs,
		})
	}
	userRows.Close()

	// Time by task
	taskRows, _ := h.db.Query(`
		SELECT t.id, t.title,
		       SUM(EXTRACT(EPOCH FROM (COALESCE(tl.ended_at, NOW()) - tl.started_at)))::bigint as secs
		FROM time_logs tl
		JOIN tasks t ON t.id = tl.task_id
		WHERE tl.started_at >= $1
		GROUP BY t.id, t.title
		ORDER BY secs DESC
		LIMIT 50`, since)
	byTask := []fiber.Map{}
	for taskRows.Next() {
		var id int
		var title string
		var secs int64
		taskRows.Scan(&id, &title, &secs)
		byTask = append(byTask, fiber.Map{"id": id, "title": title, "seconds": secs})
	}
	taskRows.Close()

	return c.JSON(fiber.Map{
		"period":   period,
		"by_user":  byUser,
		"by_task":  byTask,
	})
}

func (h *AnalyticsHandler) TV(c *fiber.Ctx) error {
	period := c.Query("period", "week")
	since := periodStart(period)

	// Active tasks
	activeRows, _ := h.db.Query(`
		SELECT t.id, t.title, u.full_name, u.username
		FROM tasks t
		LEFT JOIN users u ON u.id = t.assigned_to_id
		WHERE t.status = 'in_progress' AND t.is_archived = false
		ORDER BY t.created_at`)
	active := []fiber.Map{}
	for activeRows.Next() {
		var id int
		var title, fullName, username string
		activeRows.Scan(&id, &title, &fullName, &username)
		active = append(active, fiber.Map{
			"id": id, "title": title,
			"assigned_to": fiber.Map{"full_name": fullName, "username": username},
		})
	}
	activeRows.Close()

	// Overdue
	overdueRows, _ := h.db.Query(`
		SELECT t.id, t.title, t.deadline, u.full_name
		FROM tasks t
		LEFT JOIN users u ON u.id = t.assigned_to_id
		WHERE t.is_archived = false AND t.status != 'done'
		AND t.deadline < NOW()
		ORDER BY t.deadline LIMIT 10`)
	overdue := []fiber.Map{}
	for overdueRows.Next() {
		var id int
		var title, fullName string
		var deadline time.Time
		overdueRows.Scan(&id, &title, &deadline, &fullName)
		overdue = append(overdue, fiber.Map{
			"id": id, "title": title, "deadline": deadline,
			"assigned_to": fiber.Map{"full_name": fullName},
		})
	}
	overdueRows.Close()

	// Top performers for period
	perfRows, _ := h.db.Query(`
		SELECT u.id, u.full_name, COUNT(t.id) as cnt
		FROM users u
		JOIN tasks t ON t.assigned_to_id = u.id
		WHERE t.status = 'done' AND t.completed_at >= $1
		GROUP BY u.id, u.full_name
		ORDER BY cnt DESC LIMIT 5`, since)
	performers := []fiber.Map{}
	for perfRows.Next() {
		var id int
		var name string
		var cnt int
		perfRows.Scan(&id, &name, &cnt)
		performers = append(performers, fiber.Map{"id": id, "full_name": name, "count": cnt})
	}
	perfRows.Close()

	// Recent completions
	recentRows, _ := h.db.Query(`
		SELECT t.id, t.title, t.completed_at, u.full_name
		FROM tasks t
		LEFT JOIN users u ON u.id = t.assigned_to_id
		WHERE t.status = 'done' AND t.completed_at >= $1
		ORDER BY t.completed_at DESC LIMIT 10`, since)
	recent := []fiber.Map{}
	for recentRows.Next() {
		var id int
		var title, fullName string
		var completedAt time.Time
		recentRows.Scan(&id, &title, &completedAt, &fullName)
		recent = append(recent, fiber.Map{
			"id": id, "title": title, "completed_at": completedAt,
			"assigned_to": fiber.Map{"full_name": fullName},
		})
	}
	recentRows.Close()

	// Stats
	var totalActive, totalDone, totalOverdue int
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks WHERE status = 'in_progress' AND is_archived = false`).Scan(&totalActive)
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks WHERE status = 'done' AND completed_at >= $1`, since).Scan(&totalDone)
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks WHERE status != 'done' AND deadline < NOW() AND is_archived = false`).Scan(&totalOverdue)

	return c.JSON(fiber.Map{
		"period":          period,
		"active_tasks":    active,
		"overdue_tasks":   overdue,
		"top_performers":  performers,
		"recent_done":     recent,
		"stats": fiber.Map{
			"active":  totalActive,
			"done":    totalDone,
			"overdue": totalOverdue,
		},
	})
}

func (h *AnalyticsHandler) ExportExcel(c *fiber.Ctx) error {
	rows, err := h.db.Query(`
		SELECT t.id, t.title, t.status, t.urgency, t.task_type,
		       COALESCE(u.full_name, ''), COALESCE(d.name, ''),
		       t.deadline, t.created_at, t.completed_at
		FROM tasks t
		LEFT JOIN users u ON u.id = t.assigned_to_id
		LEFT JOIN departments d ON d.id = t.department_id
		WHERE t.is_archived = false
		ORDER BY t.created_at DESC`)
	if err != nil {
		return err
	}
	defer rows.Close()

	f := excelize.NewFile()
	sheet := "Задачи"
	f.NewSheet(sheet)
	f.DeleteSheet("Sheet1")

	headers := []string{"ID", "Заголовок", "Статус", "Приоритет", "Тип", "Исполнитель", "Отдел", "Дедлайн", "Создана", "Завершена"}
	for i, h := range headers {
		cell, _ := excelize.CoordinatesToCellName(i+1, 1)
		f.SetCellValue(sheet, cell, h)
	}

	row := 2
	for rows.Next() {
		var id int
		var title, status, urgency string
		var taskType, assigned, dept string
		var deadline, createdAt, completedAt interface{}
		rows.Scan(&id, &title, &status, &urgency, &taskType, &assigned, &dept, &deadline, &createdAt, &completedAt)

		vals := []interface{}{id, title, status, urgency, taskType, assigned, dept, deadline, createdAt, completedAt}
		for col, v := range vals {
			cell, _ := excelize.CoordinatesToCellName(col+1, row)
			f.SetCellValue(sheet, cell, v)
		}
		row++
	}

	c.Set("Content-Disposition", `attachment; filename="tasks.xlsx"`)
	c.Set("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
	buf, _ := f.WriteToBuffer()
	return c.Send(buf.Bytes())
}
