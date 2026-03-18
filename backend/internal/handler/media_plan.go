package handler

import (
	"database/sql"
	"encoding/json"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/xuri/excelize/v2"
)

type MediaPlanHandler struct {
	db *sql.DB
}

func NewMediaPlanHandler(db *sql.DB) *MediaPlanHandler {
	return &MediaPlanHandler{db: db}
}

func (h *MediaPlanHandler) Calendar(c *fiber.Ctx) error {
	// Optional month filter: ?year=2024&month=3
	now := time.Now()
	year := c.QueryInt("year", now.Year())
	month := c.QueryInt("month", int(now.Month()))

	start := time.Date(year, time.Month(month), 1, 0, 0, 0, 0, time.UTC)
	end := start.AddDate(0, 1, 0)

	rows, err := h.db.Query(`
		SELECT id, title, status, urgency, dynamic_fields,
		       assigned_to_id, department_id
		FROM tasks
		WHERE task_type = 'publication'
		AND is_archived = false
		AND (dynamic_fields->>'pub_date') IS NOT NULL
		ORDER BY dynamic_fields->>'pub_date'`)
	if err != nil {
		return err
	}
	defer rows.Close()

	type entry struct {
		ID            int                    `json:"id"`
		Title         string                 `json:"title"`
		Status        string                 `json:"status"`
		Urgency       string                 `json:"urgency"`
		DynamicFields map[string]interface{} `json:"dynamic_fields"`
		AssignedToID  *int                   `json:"assigned_to_id,omitempty"`
		DepartmentID  *int                   `json:"department_id,omitempty"`
		PubDate       string                 `json:"pub_date"`
	}

	var entries []entry
	for rows.Next() {
		var e entry
		var dfRaw []byte
		var assignedTo, deptID sql.NullInt64
		if err := rows.Scan(&e.ID, &e.Title, &e.Status, &e.Urgency, &dfRaw, &assignedTo, &deptID); err != nil {
			continue
		}
		if len(dfRaw) > 0 {
			json.Unmarshal(dfRaw, &e.DynamicFields)
		}
		if e.DynamicFields == nil {
			e.DynamicFields = map[string]interface{}{}
		}
		pubDate, _ := e.DynamicFields["pub_date"].(string)
		if pubDate == "" {
			continue
		}
		// Filter by requested month
		pd, err := time.Parse("2006-01-02", pubDate)
		if err != nil {
			continue
		}
		if pd.Before(start) || !pd.Before(end) {
			continue
		}
		e.PubDate = pubDate
		if assignedTo.Valid {
			v := int(assignedTo.Int64)
			e.AssignedToID = &v
		}
		if deptID.Valid {
			v := int(deptID.Int64)
			e.DepartmentID = &v
		}
		entries = append(entries, e)
	}

	return c.JSON(fiber.Map{
		"year":    year,
		"month":   month,
		"entries": entries,
	})
}

func (h *MediaPlanHandler) ExportExcel(c *fiber.Ctx) error {
	now := time.Now()
	year := c.QueryInt("year", now.Year())
	month := c.QueryInt("month", int(now.Month()))

	start := time.Date(year, time.Month(month), 1, 0, 0, 0, 0, time.UTC)
	end := start.AddDate(0, 1, 0)

	rows, err := h.db.Query(`
		SELECT t.title, t.status, t.urgency,
		       t.dynamic_fields->>'pub_date',
		       COALESCE(u.full_name, ''),
		       COALESCE(d.name, '')
		FROM tasks t
		LEFT JOIN users u ON u.id = t.assigned_to_id
		LEFT JOIN departments d ON d.id = t.department_id
		WHERE t.task_type = 'publication'
		AND t.is_archived = false
		AND (t.dynamic_fields->>'pub_date') IS NOT NULL
		AND (t.dynamic_fields->>'pub_date')::date >= $1
		AND (t.dynamic_fields->>'pub_date')::date < $2
		ORDER BY (t.dynamic_fields->>'pub_date')::date`, start, end)
	if err != nil {
		return err
	}
	defer rows.Close()

	f := excelize.NewFile()
	sheet := "Медиаплан"
	f.NewSheet(sheet)
	f.DeleteSheet("Sheet1")

	headers := []string{"Заголовок", "Статус", "Приоритет", "Дата публикации", "Исполнитель", "Отдел"}
	for i, h := range headers {
		cell, _ := excelize.CoordinatesToCellName(i+1, 1)
		f.SetCellValue(sheet, cell, h)
	}

	row := 2
	for rows.Next() {
		var title, status, urgency, pubDate, assigned, dept string
		rows.Scan(&title, &status, &urgency, &pubDate, &assigned, &dept)
		for col, v := range []interface{}{title, status, urgency, pubDate, assigned, dept} {
			cell, _ := excelize.CoordinatesToCellName(col+1, row)
			f.SetCellValue(sheet, cell, v)
		}
		row++
	}

	c.Set("Content-Disposition", `attachment; filename="media_plan.xlsx"`)
	c.Set("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
	buf, _ := f.WriteToBuffer()
	return c.Send(buf.Bytes())
}
