package repository

import (
	"database/sql"
	"errors"

	"github.com/lib/pq"
	"gw1/backend/internal/domain"
)

type RhythmRepo struct {
	db *sql.DB
}

func NewRhythmRepo(db *sql.DB) *RhythmRepo {
	return &RhythmRepo{db: db}
}

type CreateRhythmInput struct {
	Name            string
	Description     string
	Frequency       domain.Frequency
	DayOfWeek       *int
	DayOfMonth      *int
	TaskTitle       string
	TaskDescription string
	TaskUrgency     domain.Urgency
	TaskType        *string
	TaskTags        []string
	DepartmentID    *int
}

type UpdateRhythmInput = CreateRhythmInput

func scanRhythm(row interface{ Scan(...interface{}) error }) (*domain.Rhythm, error) {
	r := &domain.Rhythm{}
	var (
		taskType              sql.NullString
		dayOfWeek, dayOfMonth sql.NullInt64
		departmentID          sql.NullInt64
		lastRunAt             sql.NullTime
		deptID                sql.NullInt64
		deptName              sql.NullString
		tags                  []string
	)
	err := row.Scan(
		&r.ID, &r.Name, &r.Description, &r.Frequency,
		&dayOfWeek, &dayOfMonth,
		&r.TaskTitle, &r.TaskDescription, &r.TaskUrgency, &taskType,
		pq.Array(&tags), &departmentID,
		&r.CreatedByID, &r.IsActive, &lastRunAt, &r.CreatedAt,
		&deptID, &deptName,
	)
	if err != nil {
		return nil, err
	}
	r.TaskType = ns(taskType)
	r.DayOfWeek = ni(dayOfWeek)
	r.DayOfMonth = ni(dayOfMonth)
	r.DepartmentID = ni(departmentID)
	r.LastRunAt = nt(lastRunAt)
	r.TaskTags = tags
	if r.TaskTags == nil {
		r.TaskTags = []string{}
	}
	if deptID.Valid {
		r.Department = &domain.Department{ID: int(deptID.Int64), Name: deptName.String}
	}
	return r, nil
}

const rhythmSelect = `
	SELECT r.id, r.name, r.description, r.frequency,
	       r.day_of_week, r.day_of_month,
	       r.task_title, r.task_description, r.task_urgency, r.task_type,
	       r.task_tags, r.department_id,
	       r.created_by_id, r.is_active, r.last_run_at, r.created_at,
	       d.id, d.name
	FROM rhythms r
	LEFT JOIN departments d ON d.id = r.department_id`

func (r *RhythmRepo) FindAll() ([]domain.Rhythm, error) {
	rows, err := r.db.Query(rhythmSelect + ` ORDER BY r.name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var rhythms []domain.Rhythm
	for rows.Next() {
		rh, err := scanRhythm(rows)
		if err != nil {
			return nil, err
		}
		rhythms = append(rhythms, *rh)
	}
	return rhythms, rows.Err()
}

func (r *RhythmRepo) FindByID(id int) (*domain.Rhythm, error) {
	row := r.db.QueryRow(rhythmSelect+` WHERE r.id = $1`, id)
	rh, err := scanRhythm(row)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return rh, err
}

func (r *RhythmRepo) Create(inp *CreateRhythmInput, createdByID int) (*domain.Rhythm, error) {
	var id int
	err := r.db.QueryRow(`
		INSERT INTO rhythms
			(name, description, frequency, day_of_week, day_of_month,
			 task_title, task_description, task_urgency, task_type, task_tags,
			 department_id, created_by_id)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
		RETURNING id`,
		inp.Name, inp.Description, inp.Frequency, inp.DayOfWeek, inp.DayOfMonth,
		inp.TaskTitle, inp.TaskDescription, inp.TaskUrgency, inp.TaskType,
		pq.Array(inp.TaskTags), inp.DepartmentID, createdByID,
	).Scan(&id)
	if err != nil {
		return nil, err
	}
	return r.FindByID(id)
}

func (r *RhythmRepo) Update(id int, inp *UpdateRhythmInput) (*domain.Rhythm, error) {
	_, err := r.db.Exec(`
		UPDATE rhythms SET
			name=$1, description=$2, frequency=$3, day_of_week=$4, day_of_month=$5,
			task_title=$6, task_description=$7, task_urgency=$8, task_type=$9,
			task_tags=$10, department_id=$11
		WHERE id = $12`,
		inp.Name, inp.Description, inp.Frequency, inp.DayOfWeek, inp.DayOfMonth,
		inp.TaskTitle, inp.TaskDescription, inp.TaskUrgency, inp.TaskType,
		pq.Array(inp.TaskTags), inp.DepartmentID, id,
	)
	if err != nil {
		return nil, err
	}
	return r.FindByID(id)
}

func (r *RhythmRepo) Toggle(id int, active bool) error {
	_, err := r.db.Exec(`UPDATE rhythms SET is_active = $1 WHERE id = $2`, active, id)
	return err
}

func (r *RhythmRepo) UpdateLastRun(id int) error {
	_, err := r.db.Exec(`UPDATE rhythms SET last_run_at = NOW() WHERE id = $1`, id)
	return err
}

func (r *RhythmRepo) Delete(id int) error {
	res, err := r.db.Exec(`DELETE FROM rhythms WHERE id = $1`, id)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrNotFound
	}
	return nil
}
