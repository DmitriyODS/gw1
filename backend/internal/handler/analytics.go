package handler

import (
	"database/sql"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/xuri/excelize/v2"
	"gw1/backend/internal/middleware"
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

	// Top performers by completed tasks in period
	topTasksRows, _ := h.db.Query(`
		SELECT u.id, u.full_name, u.username, COUNT(t.id) as cnt
		FROM users u
		JOIN tasks t ON t.assigned_to_id = u.id
		WHERE t.status = 'done' AND t.completed_at >= $1
		GROUP BY u.id, u.full_name, u.username
		ORDER BY cnt DESC LIMIT 10`, since)
	topByTasks := []fiber.Map{}
	for topTasksRows.Next() {
		var id int
		var fullName, username string
		var cnt int
		topTasksRows.Scan(&id, &fullName, &username, &cnt)
		topByTasks = append(topByTasks, fiber.Map{"id": id, "full_name": fullName, "username": username, "count": cnt})
	}
	topTasksRows.Close()

	// Top performers by time logged in period
	topTimeRows, _ := h.db.Query(`
		SELECT u.id, u.full_name, u.username,
		       SUM(EXTRACT(EPOCH FROM (COALESCE(tl.ended_at, NOW()) - tl.started_at)))::bigint as secs
		FROM time_logs tl
		JOIN users u ON u.id = tl.user_id
		WHERE tl.started_at >= $1
		GROUP BY u.id, u.full_name, u.username
		ORDER BY secs DESC LIMIT 10`, since)
	topByTime := []fiber.Map{}
	for topTimeRows.Next() {
		var id int
		var fullName, username string
		var secs int64
		topTimeRows.Scan(&id, &fullName, &username, &secs)
		topByTime = append(topByTime, fiber.Map{"id": id, "full_name": fullName, "username": username, "seconds": secs})
	}
	topTimeRows.Close()

	// Top customers by number of requests
	topCustRows, _ := h.db.Query(`
		SELECT COALESCE(customer_name, 'Аноним'), COUNT(*) as cnt
		FROM tasks
		WHERE created_at >= $1 AND customer_name IS NOT NULL AND customer_name != ''
		GROUP BY customer_name
		ORDER BY cnt DESC LIMIT 10`, since)
	topCustomers := []fiber.Map{}
	for topCustRows.Next() {
		var name string
		var cnt int
		topCustRows.Scan(&name, &cnt)
		topCustomers = append(topCustomers, fiber.Map{"name": name, "count": cnt})
	}
	topCustRows.Close()

	// Top departments by incoming tasks
	topDeptRows, _ := h.db.Query(`
		SELECT COALESCE(d.name, 'Без отдела'), COUNT(t.id) as cnt
		FROM tasks t
		LEFT JOIN departments d ON d.id = t.department_id
		WHERE t.created_at >= $1
		GROUP BY d.name
		ORDER BY cnt DESC LIMIT 10`, since)
	topDepts := []fiber.Map{}
	for topDeptRows.Next() {
		var name string
		var cnt int
		topDeptRows.Scan(&name, &cnt)
		topDepts = append(topDepts, fiber.Map{"name": name, "count": cnt})
	}
	topDeptRows.Close()

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
		"period":          period,
		"by_status":       byStatus,
		"by_department":   byDept,
		"by_type":         byType,
		"top_by_tasks":    topByTasks,
		"top_by_time":     topByTime,
		"top_customers":   topCustomers,
		"top_departments": topDepts,
		"burnup_created":  burnupCreated,
		"burnup_done":     burnupDone,
		"overdue_count":   overdueCount,
	})
}

func (h *AnalyticsHandler) TimeReport(c *fiber.Ctx) error {
	claims := middleware.GetClaims(c)

	// Support from/to date params (preferred) or period
	var since, until time.Time
	now := time.Now()

	if from := c.Query("from"); from != "" {
		since, _ = time.Parse("2006-01-02", from)
	}
	if to := c.Query("to"); to != "" {
		t, err := time.Parse("2006-01-02", to)
		if err == nil {
			until = t.Add(24 * time.Hour)
		}
	}
	if since.IsZero() {
		since = periodStart(c.Query("period", "month"))
	}
	if until.IsZero() {
		until = now
	}

	// Optional user filter (admin+ can filter by any user, staff sees only self)
	userFilter := 0
	if claims.Role.CanAdmin() {
		userFilter = c.QueryInt("user_id", 0)
	}

	// Summary: total seconds this week / this month / all time for current user or filtered user
	summaryUserID := claims.UserID
	if userFilter != 0 {
		summaryUserID = userFilter
	}
	var totalWeek, totalMonth, totalAll int64
	weekStart := now.AddDate(0, 0, -7)
	monthStart := now.AddDate(0, -1, 0)
	h.db.QueryRow(`SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, NOW()) - started_at))::bigint), 0) FROM time_logs WHERE user_id = $1 AND started_at >= $2`, summaryUserID, weekStart).Scan(&totalWeek)
	h.db.QueryRow(`SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, NOW()) - started_at))::bigint), 0) FROM time_logs WHERE user_id = $1 AND started_at >= $2`, summaryUserID, monthStart).Scan(&totalMonth)
	h.db.QueryRow(`SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, NOW()) - started_at))::bigint), 0) FROM time_logs WHERE user_id = $1`, summaryUserID).Scan(&totalAll)

	// Detailed logs
	detailArgs := []interface{}{since, until}
	detailWhere := "tl.started_at >= $1 AND tl.started_at < $2"
	if userFilter != 0 {
		detailWhere += " AND tl.user_id = $3"
		detailArgs = append(detailArgs, userFilter)
	} else if !claims.Role.CanAdmin() {
		detailWhere += " AND tl.user_id = $3"
		detailArgs = append(detailArgs, claims.UserID)
	}

	detailRows, err := h.db.Query(`
		SELECT tl.id, tl.task_id, t.title, tl.user_id, u.full_name,
		       COALESCE(d.name, ''), tl.started_at, tl.ended_at
		FROM time_logs tl
		JOIN tasks t ON t.id = tl.task_id
		JOIN users u ON u.id = tl.user_id
		LEFT JOIN departments d ON d.id = t.department_id
		WHERE `+detailWhere+`
		ORDER BY tl.started_at DESC
		LIMIT 500`, detailArgs...)
	details := []fiber.Map{}
	if err == nil {
		defer detailRows.Close()
		for detailRows.Next() {
			var logID, taskID, userID int
			var taskTitle, userName, deptName string
			var startedAt time.Time
			var endedAt sql.NullTime
			detailRows.Scan(&logID, &taskID, &taskTitle, &userID, &userName, &deptName, &startedAt, &endedAt)
			var secs int64
			if endedAt.Valid {
				secs = int64(endedAt.Time.Sub(startedAt).Seconds())
			} else {
				secs = int64(now.Sub(startedAt).Seconds())
			}
			details = append(details, fiber.Map{
				"id":          logID,
				"task_id":     taskID,
				"task_title":  taskTitle,
				"user_id":     userID,
				"user_name":   userName,
				"department":  deptName,
				"started_at":  startedAt,
				"ended_at":    endedAt.Time,
				"is_active":   !endedAt.Valid,
				"seconds":     secs,
			})
		}
	}

	// Time by user (for summary table)
	byUserArgs := []interface{}{since, until}
	byUserWhere := "tl.started_at >= $1 AND tl.started_at < $2"
	if !claims.Role.CanAdmin() {
		byUserWhere += " AND tl.user_id = $3"
		byUserArgs = append(byUserArgs, claims.UserID)
	}
	userRows, _ := h.db.Query(`
		SELECT u.id, u.full_name, u.username,
		       SUM(EXTRACT(EPOCH FROM (COALESCE(tl.ended_at, NOW()) - tl.started_at)))::bigint as secs
		FROM time_logs tl
		JOIN users u ON u.id = tl.user_id
		WHERE `+byUserWhere+`
		GROUP BY u.id, u.full_name, u.username
		ORDER BY secs DESC`, byUserArgs...)
	byUser := []fiber.Map{}
	if userRows != nil {
		defer userRows.Close()
		for userRows.Next() {
			var id int
			var fullName, username string
			var secs int64
			userRows.Scan(&id, &fullName, &username, &secs)
			byUser = append(byUser, fiber.Map{
				"id": id, "full_name": fullName, "username": username, "seconds": secs,
			})
		}
	}

	// Top tasks by time
	taskArgs := []interface{}{since, until}
	taskWhere := "tl.started_at >= $1 AND tl.started_at < $2"
	if !claims.Role.CanAdmin() {
		taskWhere += " AND tl.user_id = $3"
		taskArgs = append(taskArgs, claims.UserID)
	}
	taskRows, _ := h.db.Query(`
		SELECT t.id, t.title,
		       SUM(EXTRACT(EPOCH FROM (COALESCE(tl.ended_at, NOW()) - tl.started_at)))::bigint as secs
		FROM time_logs tl
		JOIN tasks t ON t.id = tl.task_id
		WHERE `+taskWhere+`
		GROUP BY t.id, t.title
		ORDER BY secs DESC
		LIMIT 20`, taskArgs...)
	byTask := []fiber.Map{}
	if taskRows != nil {
		defer taskRows.Close()
		for taskRows.Next() {
			var id int
			var title string
			var secs int64
			taskRows.Scan(&id, &title, &secs)
			byTask = append(byTask, fiber.Map{"id": id, "title": title, "seconds": secs})
		}
	}

	return c.JSON(fiber.Map{
		"period":       c.Query("period", "month"),
		"by_user":      byUser,
		"by_task":      byTask,
		"detail_logs":  details,
		"summary": fiber.Map{
			"week_seconds":  totalWeek,
			"month_seconds": totalMonth,
			"all_seconds":   totalAll,
		},
	})
}

func (h *AnalyticsHandler) TV(c *fiber.Ctx) error {
	period := c.Query("period", "week")
	since := periodStart(period)
	now := time.Now()
	todayStart := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())

	// Active tasks
	activeRows, _ := h.db.Query(`
		SELECT t.id, t.title, t.urgency, u.full_name, u.username
		FROM tasks t
		LEFT JOIN users u ON u.id = t.assigned_to_id
		WHERE t.status = 'in_progress' AND t.is_archived = false
		ORDER BY t.created_at`)
	active := []fiber.Map{}
	for activeRows.Next() {
		var id int
		var title, urgency string
		var fullName, username string
		activeRows.Scan(&id, &title, &urgency, &fullName, &username)
		active = append(active, fiber.Map{
			"id": id, "title": title, "urgency": urgency,
			"assigned_to": fiber.Map{"full_name": fullName, "username": username},
		})
	}
	activeRows.Close()

	// Overdue (max 6)
	overdueRows, _ := h.db.Query(`
		SELECT t.id, t.title, t.deadline, t.urgency, COALESCE(u.full_name, '')
		FROM tasks t
		LEFT JOIN users u ON u.id = t.assigned_to_id
		WHERE t.is_archived = false AND t.status != 'done'
		AND t.deadline < NOW()
		ORDER BY t.deadline LIMIT 6`)
	overdue := []fiber.Map{}
	for overdueRows.Next() {
		var id int
		var title, urgency, fullName string
		var deadline time.Time
		overdueRows.Scan(&id, &title, &deadline, &urgency, &fullName)
		overdue = append(overdue, fiber.Map{
			"id": id, "title": title, "deadline": deadline, "urgency": urgency,
			"assigned_to": fiber.Map{"full_name": fullName},
		})
	}
	overdueRows.Close()

	// Top performers for period (by completed tasks)
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

	// Top by time for period
	topTimeRows, _ := h.db.Query(`
		SELECT u.id, u.full_name,
		       SUM(EXTRACT(EPOCH FROM (COALESCE(tl.ended_at, NOW()) - tl.started_at)))::bigint as secs
		FROM time_logs tl
		JOIN users u ON u.id = tl.user_id
		WHERE tl.started_at >= $1
		GROUP BY u.id, u.full_name
		ORDER BY secs DESC LIMIT 5`, since)
	topByTime := []fiber.Map{}
	for topTimeRows.Next() {
		var id int
		var name string
		var secs int64
		topTimeRows.Scan(&id, &name, &secs)
		topByTime = append(topByTime, fiber.Map{"id": id, "full_name": name, "seconds": secs})
	}
	topTimeRows.Close()

	// By department (active tasks)
	byDeptRows, _ := h.db.Query(`
		SELECT COALESCE(d.name, 'Без отдела'), COUNT(t.id)
		FROM tasks t
		LEFT JOIN departments d ON d.id = t.department_id
		WHERE t.is_archived = false
		GROUP BY d.name ORDER BY COUNT(t.id) DESC`)
	byDept := []fiber.Map{}
	for byDeptRows.Next() {
		var name string
		var n int
		byDeptRows.Scan(&name, &n)
		byDept = append(byDept, fiber.Map{"name": name, "count": n})
	}
	byDeptRows.Close()

	// By type (active tasks)
	byTypeRows, _ := h.db.Query(`
		SELECT COALESCE(task_type, 'Без типа'), COUNT(*)
		FROM tasks WHERE is_archived = false AND status != 'done'
		GROUP BY task_type ORDER BY COUNT(*) DESC`)
	byType := []fiber.Map{}
	for byTypeRows.Next() {
		var name string
		var n int
		byTypeRows.Scan(&name, &n)
		byType = append(byType, fiber.Map{"name": name, "count": n})
	}
	byTypeRows.Close()

	// Today stats
	var todayCreated, todayDone, todayInProgress, todayOverdue int
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks WHERE created_at >= $1 AND is_archived = false`, todayStart).Scan(&todayCreated)
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks WHERE completed_at >= $1 AND status = 'done'`, todayStart).Scan(&todayDone)
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks WHERE status = 'in_progress' AND is_archived = false`).Scan(&todayInProgress)
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks WHERE status != 'done' AND deadline < NOW() AND is_archived = false`).Scan(&todayOverdue)

	// Concentration record: longest ended session
	var concUserName string
	var concSeconds int64
	var concTaskTitle string
	h.db.QueryRow(`
		SELECT u.full_name, t.title,
		       EXTRACT(EPOCH FROM (tl.ended_at - tl.started_at))::bigint as secs
		FROM time_logs tl
		JOIN users u ON u.id = tl.user_id
		JOIN tasks t ON t.id = tl.task_id
		WHERE tl.ended_at IS NOT NULL
		ORDER BY secs DESC LIMIT 1`).Scan(&concUserName, &concTaskTitle, &concSeconds)

	// Burnup for period
	burnCreatedRows, _ := h.db.Query(`
		SELECT DATE(created_at), COUNT(*) FROM tasks
		WHERE created_at >= $1 GROUP BY DATE(created_at) ORDER BY DATE(created_at)`, since)
	burnupCreated := []fiber.Map{}
	for burnCreatedRows.Next() {
		var d time.Time
		var n int
		burnCreatedRows.Scan(&d, &n)
		burnupCreated = append(burnupCreated, fiber.Map{"date": d.Format("2006-01-02"), "count": n})
	}
	burnCreatedRows.Close()

	burnDoneRows, _ := h.db.Query(`
		SELECT DATE(completed_at), COUNT(*) FROM tasks
		WHERE completed_at >= $1 GROUP BY DATE(completed_at) ORDER BY DATE(completed_at)`, since)
	burnupDone := []fiber.Map{}
	for burnDoneRows.Next() {
		var d time.Time
		var n int
		burnDoneRows.Scan(&d, &n)
		burnupDone = append(burnupDone, fiber.Map{"date": d.Format("2006-01-02"), "count": n})
	}
	burnDoneRows.Close()

	// Stats
	var totalActive, totalDone, totalOverdue int
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks WHERE status = 'in_progress' AND is_archived = false`).Scan(&totalActive)
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks WHERE status = 'done' AND completed_at >= $1`, since).Scan(&totalDone)
	h.db.QueryRow(`SELECT COUNT(*) FROM tasks WHERE status != 'done' AND deadline < NOW() AND is_archived = false`).Scan(&totalOverdue)

	return c.JSON(fiber.Map{
		"period":         period,
		"active_tasks":   active,
		"overdue_tasks":  overdue,
		"top_performers": performers,
		"top_by_time":    topByTime,
		"by_department":  byDept,
		"by_type":        byType,
		"burnup_created": burnupCreated,
		"burnup_done":    burnupDone,
		"today": fiber.Map{
			"created":     todayCreated,
			"done":        todayDone,
			"in_progress": todayInProgress,
			"overdue":     todayOverdue,
		},
		"concentration_record": fiber.Map{
			"user_name":  concUserName,
			"task_title": concTaskTitle,
			"seconds":    concSeconds,
		},
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
		       COALESCE(t.customer_name, ''), COALESCE(t.customer_phone, ''),
		       t.deadline, t.created_at, t.completed_at,
		       COALESCE(
		         (SELECT SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, NOW()) - started_at))::bigint)
		          FROM time_logs WHERE task_id = t.id), 0
		       ) as total_secs
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

	headers := []string{
		"ID", "Заголовок", "Статус", "Приоритет", "Тип",
		"Исполнитель", "Отдел", "Заказчик", "Телефон",
		"Дедлайн", "Создана", "Завершена", "Время (мин)",
	}
	for i, h := range headers {
		cell, _ := excelize.CoordinatesToCellName(i+1, 1)
		f.SetCellValue(sheet, cell, h)
	}

	row := 2
	for rows.Next() {
		var id int
		var title, status, urgency, taskType, assigned, dept, customer, phone string
		var deadline, createdAt, completedAt interface{}
		var totalSecs int64
		rows.Scan(&id, &title, &status, &urgency, &taskType,
			&assigned, &dept, &customer, &phone,
			&deadline, &createdAt, &completedAt, &totalSecs)

		vals := []interface{}{
			id, title, status, urgency, taskType, assigned, dept, customer, phone,
			deadline, createdAt, completedAt, totalSecs / 60,
		}
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
