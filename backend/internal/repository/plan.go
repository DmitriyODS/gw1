package repository

import (
	"database/sql"
	"encoding/json"
	"errors"
	"time"

	"github.com/lib/pq"
	"gw1/backend/internal/domain"
)

type PlanRepo struct {
	db *sql.DB
}

func NewPlanRepo(db *sql.DB) *PlanRepo {
	return &PlanRepo{db: db}
}

type CreatePlanInput struct {
	Title         string
	Description   string
	CustomerName  *string
	CustomerPhone *string
	CustomerEmail *string
	ReleaseDate   *time.Time
	TaskType      *string
	Urgency       domain.Urgency
	Tags          []string
	DynamicFields map[string]interface{}
	GroupID       *int
	DepartmentID  *int
}

type UpdatePlanInput = CreatePlanInput

func scanPlan(row interface{ Scan(...interface{}) error }) (*domain.Plan, error) {
	p := &domain.Plan{}
	var (
		customerName, customerPhone, customerEmail sql.NullString
		releaseDate                                sql.NullTime
		taskType                                   sql.NullString
		groupID, departmentID, convertedTaskID     sql.NullInt64
		tags                                       []string
		dfRaw                                      []byte
		deptID                                     sql.NullInt64
		deptName                                   sql.NullString
		grpID                                      sql.NullInt64
		grpName                                    sql.NullString
	)
	err := row.Scan(
		&p.ID, &p.Title, &p.Description,
		&customerName, &customerPhone, &customerEmail,
		&releaseDate, &taskType, &p.Urgency,
		pq.Array(&tags), &dfRaw,
		&groupID, &departmentID,
		&p.CreatedByID, &p.IsConverted, &convertedTaskID, &p.CreatedAt,
		&deptID, &deptName,
		&grpID, &grpName,
	)
	if err != nil {
		return nil, err
	}
	p.CustomerName = ns(customerName)
	p.CustomerPhone = ns(customerPhone)
	p.CustomerEmail = ns(customerEmail)
	p.ReleaseDate = nt(releaseDate)
	p.TaskType = ns(taskType)
	p.GroupID = ni(groupID)
	p.DepartmentID = ni(departmentID)
	p.ConvertedTaskID = ni(convertedTaskID)
	p.Tags = tags
	if p.Tags == nil {
		p.Tags = []string{}
	}
	if len(dfRaw) > 0 {
		json.Unmarshal(dfRaw, &p.DynamicFields)
	}
	if p.DynamicFields == nil {
		p.DynamicFields = map[string]interface{}{}
	}
	if deptID.Valid {
		p.Department = &domain.Department{ID: int(deptID.Int64), Name: deptName.String}
	}
	if grpID.Valid {
		p.Group = &domain.PlanGroup{ID: int(grpID.Int64), Name: grpName.String}
	}
	return p, nil
}

const planSelect = `
	SELECT p.id, p.title, p.description,
	       p.customer_name, p.customer_phone, p.customer_email,
	       p.release_date, p.task_type, p.urgency,
	       p.tags, p.dynamic_fields,
	       p.group_id, p.department_id,
	       p.created_by_id, p.is_converted, p.converted_task_id, p.created_at,
	       d.id, d.name,
	       g.id, g.name
	FROM plans p
	LEFT JOIN departments d ON d.id = p.department_id
	LEFT JOIN plan_groups  g ON g.id = p.group_id`

func (r *PlanRepo) FindAll() ([]domain.Plan, error) {
	rows, err := r.db.Query(planSelect + ` ORDER BY p.release_date ASC NULLS LAST, p.created_at DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var plans []domain.Plan
	for rows.Next() {
		p, err := scanPlan(rows)
		if err != nil {
			return nil, err
		}
		plans = append(plans, *p)
	}
	return plans, rows.Err()
}

func (r *PlanRepo) FindDue() ([]domain.Plan, error) {
	rows, err := r.db.Query(planSelect+`
		WHERE p.is_converted = false AND p.release_date <= NOW()
		ORDER BY p.release_date`, )
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var plans []domain.Plan
	for rows.Next() {
		p, err := scanPlan(rows)
		if err != nil {
			return nil, err
		}
		plans = append(plans, *p)
	}
	return plans, rows.Err()
}

func (r *PlanRepo) FindByID(id int) (*domain.Plan, error) {
	row := r.db.QueryRow(planSelect+` WHERE p.id = $1`, id)
	p, err := scanPlan(row)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return p, err
}

func (r *PlanRepo) Create(inp *CreatePlanInput, createdByID int) (*domain.Plan, error) {
	df, _ := json.Marshal(inp.DynamicFields)
	var id int
	err := r.db.QueryRow(`
		INSERT INTO plans
			(title, description, customer_name, customer_phone, customer_email,
			 release_date, task_type, urgency, tags, dynamic_fields,
			 group_id, department_id, created_by_id)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
		RETURNING id`,
		inp.Title, inp.Description, inp.CustomerName, inp.CustomerPhone, inp.CustomerEmail,
		inp.ReleaseDate, inp.TaskType, inp.Urgency,
		pq.Array(inp.Tags), df,
		inp.GroupID, inp.DepartmentID, createdByID,
	).Scan(&id)
	if err != nil {
		return nil, err
	}
	return r.FindByID(id)
}

func (r *PlanRepo) Update(id int, inp *UpdatePlanInput) (*domain.Plan, error) {
	df, _ := json.Marshal(inp.DynamicFields)
	_, err := r.db.Exec(`
		UPDATE plans SET
			title=$1, description=$2, customer_name=$3, customer_phone=$4, customer_email=$5,
			release_date=$6, task_type=$7, urgency=$8, tags=$9, dynamic_fields=$10,
			group_id=$11, department_id=$12
		WHERE id = $13`,
		inp.Title, inp.Description, inp.CustomerName, inp.CustomerPhone, inp.CustomerEmail,
		inp.ReleaseDate, inp.TaskType, inp.Urgency,
		pq.Array(inp.Tags), df,
		inp.GroupID, inp.DepartmentID, id,
	)
	if err != nil {
		return nil, err
	}
	return r.FindByID(id)
}

func (r *PlanRepo) MarkConverted(id, taskID int) error {
	_, err := r.db.Exec(
		`UPDATE plans SET is_converted = true, converted_task_id = $1 WHERE id = $2`, taskID, id)
	return err
}

func (r *PlanRepo) Delete(id int) error {
	res, err := r.db.Exec(`DELETE FROM plans WHERE id = $1`, id)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrNotFound
	}
	return nil
}

// -- Plan groups --

func (r *PlanRepo) FindGroups() ([]domain.PlanGroup, error) {
	rows, err := r.db.Query(`SELECT id, name, created_by_id, created_at FROM plan_groups ORDER BY name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var groups []domain.PlanGroup
	for rows.Next() {
		var g domain.PlanGroup
		if err := rows.Scan(&g.ID, &g.Name, &g.CreatedByID, &g.CreatedAt); err != nil {
			return nil, err
		}
		groups = append(groups, g)
	}
	return groups, rows.Err()
}

func (r *PlanRepo) CreateGroup(name string, userID int) (*domain.PlanGroup, error) {
	g := &domain.PlanGroup{}
	err := r.db.QueryRow(`
		INSERT INTO plan_groups (name, created_by_id) VALUES ($1, $2)
		RETURNING id, name, created_by_id, created_at`, name, userID).
		Scan(&g.ID, &g.Name, &g.CreatedByID, &g.CreatedAt)
	return g, err
}

func (r *PlanRepo) DeleteGroup(id int) error {
	_, err := r.db.Exec(`DELETE FROM plan_groups WHERE id = $1`, id)
	return err
}
