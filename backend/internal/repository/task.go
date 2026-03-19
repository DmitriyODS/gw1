package repository

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/lib/pq"
	"gw1/backend/internal/domain"
)

type TaskRepo struct {
	db *sql.DB
}

func NewTaskRepo(db *sql.DB) *TaskRepo {
	return &TaskRepo{db: db}
}

type TaskFilter struct {
	Status       *domain.TaskStatus
	Urgency      *domain.Urgency
	DepartmentID *int
	AssignedToID *int
	Archived     *bool
	ParentOnly   bool     // only top-level tasks
	Tags         []string // filter tasks having ALL of these tags
	Free         bool     // only unassigned tasks
	Page         int
	PerPage      int
}

const taskSelect = `
	SELECT
		t.id, t.title, t.description, t.status, t.urgency, t.task_type,
		t.tags, t.dynamic_fields,
		t.customer_name, t.customer_phone, t.customer_email,
		t.deadline, t.created_at, t.completed_at,
		t.department_id, t.created_by_id, t.assigned_to_id, t.parent_task_id,
		t.is_archived, t.archived_at,
		u.id, u.username, u.full_name,
		au.id, au.username, au.full_name,
		d.id, d.name
	FROM tasks t
	LEFT JOIN users u  ON u.id  = t.created_by_id
	LEFT JOIN users au ON au.id = t.assigned_to_id
	LEFT JOIN departments d ON d.id = t.department_id`

func scanTask(row interface {
	Scan(...interface{}) error
}) (*domain.Task, error) {
	t := &domain.Task{}
	var (
		taskType                      sql.NullString
		customerName, customerPhone, customerEmail sql.NullString
		deadline, completedAt, archivedAt          sql.NullTime
		departmentID, assignedToID, parentTaskID   sql.NullInt64
		tagsRaw                                    []string
		dfRaw                                      []byte
		createdByUsername, createdByFullName sql.NullString
		assignedToIDN                        sql.NullInt64
		assignedUsername, assignedFullName   sql.NullString
		deptID                               sql.NullInt64
		deptName                             sql.NullString
		cbID                                 sql.NullInt64
	)

	err := row.Scan(
		&t.ID, &t.Title, &t.Description, &t.Status, &t.Urgency, &taskType,
		pq.Array(&tagsRaw), &dfRaw,
		&customerName, &customerPhone, &customerEmail,
		&deadline, &t.CreatedAt, &completedAt,
		&departmentID, &t.CreatedByID, &assignedToID, &parentTaskID,
		&t.IsArchived, &archivedAt,
		&cbID, &createdByUsername, &createdByFullName,
		&assignedToIDN, &assignedUsername, &assignedFullName,
		&deptID, &deptName,
	)
	if err != nil {
		return nil, err
	}

	t.TaskType = ns(taskType)
	t.Tags = tagsRaw
	if t.Tags == nil {
		t.Tags = []string{}
	}
	if len(dfRaw) > 0 {
		json.Unmarshal(dfRaw, &t.DynamicFields)
	}
	if t.DynamicFields == nil {
		t.DynamicFields = map[string]interface{}{}
	}
	t.CustomerName = ns(customerName)
	t.CustomerPhone = ns(customerPhone)
	t.CustomerEmail = ns(customerEmail)
	t.Deadline = nt(deadline)
	t.CompletedAt = nt(completedAt)
	t.ArchivedAt = nt(archivedAt)
	t.DepartmentID = ni(departmentID)
	t.AssignedToID = ni(assignedToID)
	t.ParentTaskID = ni(parentTaskID)

	if cbID.Valid {
		t.CreatedBy = &domain.User{
			ID:       int(cbID.Int64),
			Username: createdByUsername.String,
			FullName: createdByFullName.String,
		}
	}
	if assignedToIDN.Valid {
		t.AssignedTo = &domain.User{
			ID:       int(assignedToIDN.Int64),
			Username: assignedUsername.String,
			FullName: assignedFullName.String,
		}
	}
	if deptID.Valid {
		t.Department = &domain.Department{
			ID:   int(deptID.Int64),
			Name: deptName.String,
		}
	}
	return t, nil
}

func (r *TaskRepo) FindAll(f TaskFilter) ([]domain.Task, int, error) {
	where := []string{}
	args := []interface{}{}
	i := 1

	if f.Archived != nil {
		where = append(where, fmt.Sprintf("t.is_archived = $%d", i))
		args = append(args, *f.Archived)
		i++
	} else {
		where = append(where, "t.is_archived = false")
	}
	if f.Status != nil {
		where = append(where, fmt.Sprintf("t.status = $%d", i))
		args = append(args, *f.Status)
		i++
	}
	if f.Urgency != nil {
		where = append(where, fmt.Sprintf("t.urgency = $%d", i))
		args = append(args, *f.Urgency)
		i++
	}
	if f.DepartmentID != nil {
		where = append(where, fmt.Sprintf("t.department_id = $%d", i))
		args = append(args, *f.DepartmentID)
		i++
	}
	if f.AssignedToID != nil {
		where = append(where, fmt.Sprintf("t.assigned_to_id = $%d", i))
		args = append(args, *f.AssignedToID)
		i++
	}
	if f.ParentOnly {
		where = append(where, "t.parent_task_id IS NULL")
	}
	if len(f.Tags) > 0 {
		where = append(where, fmt.Sprintf("t.tags @> $%d", i))
		args = append(args, pq.Array(f.Tags))
		i++
	}
	if f.Free {
		where = append(where, "t.assigned_to_id IS NULL")
	}

	wClause := ""
	if len(where) > 0 {
		wClause = " WHERE " + strings.Join(where, " AND ")
	}

	// count
	var total int
	r.db.QueryRow(`SELECT COUNT(*) FROM tasks t`+wClause, args...).Scan(&total)

	// paging
	page := f.Page
	if page < 1 {
		page = 1
	}
	perPage := f.PerPage
	if perPage < 1 {
		perPage = 50
	}
	offset := (page - 1) * perPage
	args = append(args, perPage, offset)

	q := taskSelect + wClause + `
		ORDER BY
			CASE WHEN t.deadline < NOW() AND t.status != 'done' THEN 0 ELSE 1 END,
			CASE t.urgency
				WHEN 'urgent'    THEN 0
				WHEN 'important' THEN 1
				WHEN 'normal'    THEN 2
				ELSE 3
			END,
			t.deadline ASC NULLS LAST,
			t.created_at DESC
		LIMIT $` + itoa(i) + ` OFFSET $` + itoa(i+1)

	rows, err := r.db.Query(q, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var tasks []domain.Task
	for rows.Next() {
		t, err := scanTask(rows)
		if err != nil {
			return nil, 0, err
		}
		tasks = append(tasks, *t)
	}
	return tasks, total, rows.Err()
}

func (r *TaskRepo) FindByID(id int) (*domain.Task, error) {
	row := r.db.QueryRow(taskSelect+` WHERE t.id = $1`, id)
	t, err := scanTask(row)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return t, err
}

type CreateTaskInput struct {
	Title         string
	Description   string
	Urgency       domain.Urgency
	TaskType      *string
	Tags          []string
	DynamicFields map[string]interface{}
	CustomerName  *string
	CustomerPhone *string
	CustomerEmail *string
	Deadline      *time.Time
	DepartmentID  *int
	AssignedToID  *int
	ParentTaskID  *int
}

func (r *TaskRepo) Create(inp *CreateTaskInput, createdByID int) (*domain.Task, error) {
	df, _ := json.Marshal(inp.DynamicFields)
	var id int
	err := r.db.QueryRow(`
		INSERT INTO tasks
			(title, description, urgency, task_type, tags, dynamic_fields,
			 customer_name, customer_phone, customer_email, deadline,
			 department_id, created_by_id, assigned_to_id, parent_task_id)
		VALUES
			($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
		RETURNING id`,
		inp.Title, inp.Description, inp.Urgency, inp.TaskType,
		pq.Array(inp.Tags), df,
		inp.CustomerName, inp.CustomerPhone, inp.CustomerEmail, inp.Deadline,
		inp.DepartmentID, createdByID, inp.AssignedToID, inp.ParentTaskID,
	).Scan(&id)
	if err != nil {
		return nil, err
	}
	return r.FindByID(id)
}

type UpdateTaskInput struct {
	Title         *string
	Description   *string
	Urgency       *domain.Urgency
	TaskType      *string
	Tags          []string
	DynamicFields map[string]interface{}
	CustomerName  *string
	CustomerPhone *string
	CustomerEmail *string
	Deadline      *time.Time
	DepartmentID  *int
	AssignedToID  *int
}

func (r *TaskRepo) Update(id int, inp *UpdateTaskInput) (*domain.Task, error) {
	sets := []string{}
	args := []interface{}{id}
	n := 2

	add := func(col string, val interface{}) {
		sets = append(sets, fmt.Sprintf("%s = $%d", col, n))
		args = append(args, val)
		n++
	}

	if inp.Title != nil {
		add("title", *inp.Title)
	}
	if inp.Description != nil {
		add("description", *inp.Description)
	}
	if inp.Urgency != nil {
		add("urgency", *inp.Urgency)
	}
	if inp.TaskType != nil {
		add("task_type", *inp.TaskType)
	}
	if inp.Tags != nil {
		add("tags", pq.Array(inp.Tags))
	}
	if inp.DynamicFields != nil {
		df, _ := json.Marshal(inp.DynamicFields)
		add("dynamic_fields", df)
	}
	if inp.CustomerName != nil {
		add("customer_name", *inp.CustomerName)
	}
	if inp.CustomerPhone != nil {
		add("customer_phone", *inp.CustomerPhone)
	}
	if inp.CustomerEmail != nil {
		add("customer_email", *inp.CustomerEmail)
	}
	if inp.Deadline != nil {
		add("deadline", *inp.Deadline)
	}
	if inp.DepartmentID != nil {
		add("department_id", *inp.DepartmentID)
	}
	if inp.AssignedToID != nil {
		add("assigned_to_id", *inp.AssignedToID)
	}

	if len(sets) == 0 {
		return r.FindByID(id)
	}

	_, err := r.db.Exec(
		`UPDATE tasks SET `+strings.Join(sets, ", ")+` WHERE id = $1`, args...,
	)
	if err != nil {
		return nil, err
	}
	return r.FindByID(id)
}

func (r *TaskRepo) UpdateStatus(id int, status domain.TaskStatus) error {
	_, err := r.db.Exec(`UPDATE tasks SET status = $1 WHERE id = $2`, status, id)
	return err
}

func (r *TaskRepo) SetAssigned(id int, userID *int) error {
	_, err := r.db.Exec(`UPDATE tasks SET assigned_to_id = $1 WHERE id = $2`, userID, id)
	return err
}

func (r *TaskRepo) MarkDone(id int) error {
	_, err := r.db.Exec(`
		UPDATE tasks SET status = 'done', completed_at = NOW() WHERE id = $1`, id)
	return err
}

func (r *TaskRepo) Delete(id int) error {
	res, err := r.db.Exec(`DELETE FROM tasks WHERE id = $1`, id)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrNotFound
	}
	return nil
}

func (r *TaskRepo) Archive(id int) error {
	_, err := r.db.Exec(
		`UPDATE tasks SET is_archived = true, archived_at = NOW() WHERE id = $1`, id)
	return err
}

func (r *TaskRepo) FindSubtasks(parentID int) ([]domain.Task, error) {
	rows, err := r.db.Query(taskSelect+` WHERE t.parent_task_id = $1`, parentID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var tasks []domain.Task
	for rows.Next() {
		t, err := scanTask(rows)
		if err != nil {
			return nil, err
		}
		tasks = append(tasks, *t)
	}
	return tasks, rows.Err()
}

// FindAttachments returns all attachments for a task.
func (r *TaskRepo) FindAttachments(taskID int) ([]domain.TaskAttachment, error) {
	rows, err := r.db.Query(`
		SELECT id, task_id, filename, original_name, uploaded_at
		FROM task_attachments WHERE task_id = $1 ORDER BY uploaded_at`, taskID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var atts []domain.TaskAttachment
	for rows.Next() {
		var a domain.TaskAttachment
		if err := rows.Scan(&a.ID, &a.TaskID, &a.Filename, &a.OriginalName, &a.UploadedAt); err != nil {
			return nil, err
		}
		atts = append(atts, a)
	}
	return atts, rows.Err()
}

func (r *TaskRepo) CreateAttachment(taskID int, filename, originalName string) (*domain.TaskAttachment, error) {
	a := &domain.TaskAttachment{}
	err := r.db.QueryRow(`
		INSERT INTO task_attachments (task_id, filename, original_name)
		VALUES ($1, $2, $3)
		RETURNING id, task_id, filename, original_name, uploaded_at`,
		taskID, filename, originalName,
	).Scan(&a.ID, &a.TaskID, &a.Filename, &a.OriginalName, &a.UploadedAt)
	return a, err
}

func (r *TaskRepo) FindAttachmentByID(id int) (*domain.TaskAttachment, error) {
	a := &domain.TaskAttachment{}
	err := r.db.QueryRow(`
		SELECT id, task_id, filename, original_name, uploaded_at
		FROM task_attachments WHERE id = $1`, id).
		Scan(&a.ID, &a.TaskID, &a.Filename, &a.OriginalName, &a.UploadedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return a, err
}

func (r *TaskRepo) DeleteAttachment(id int) error {
	_, err := r.db.Exec(`DELETE FROM task_attachments WHERE id = $1`, id)
	return err
}

// FindComments returns all comments for a task including the author.
func (r *TaskRepo) FindComments(taskID int) ([]domain.TaskComment, error) {
	rows, err := r.db.Query(`
		SELECT c.id, c.task_id, c.user_id, c.text, c.filename, c.original_name, c.created_at,
		       u.id, u.username, u.full_name, u.avatar_path
		FROM task_comments c
		JOIN users u ON u.id = c.user_id
		WHERE c.task_id = $1
		ORDER BY c.created_at`, taskID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var comments []domain.TaskComment
	for rows.Next() {
		var c domain.TaskComment
		var filename, originalName sql.NullString
		var avatarPath sql.NullString
		u := &domain.User{}
		if err := rows.Scan(
			&c.ID, &c.TaskID, &c.UserID, &c.Text, &filename, &originalName, &c.CreatedAt,
			&u.ID, &u.Username, &u.FullName, &avatarPath,
		); err != nil {
			return nil, err
		}
		c.Filename = ns(filename)
		c.OriginalName = ns(originalName)
		u.AvatarPath = ns(avatarPath)
		c.User = u
		comments = append(comments, c)
	}
	return comments, rows.Err()
}

func (r *TaskRepo) CreateComment(taskID, userID int, text string, filename, originalName *string) (*domain.TaskComment, error) {
	c := &domain.TaskComment{}
	var fn, on sql.NullString
	err := r.db.QueryRow(`
		INSERT INTO task_comments (task_id, user_id, text, filename, original_name)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, task_id, user_id, text, filename, original_name, created_at`,
		taskID, userID, text, filename, originalName,
	).Scan(&c.ID, &c.TaskID, &c.UserID, &c.Text, &fn, &on, &c.CreatedAt)
	if err != nil {
		return nil, err
	}
	c.Filename = ns(fn)
	c.OriginalName = ns(on)
	return c, nil
}

func (r *TaskRepo) FindCommentByID(id int) (*domain.TaskComment, error) {
	c := &domain.TaskComment{}
	var fn, on sql.NullString
	err := r.db.QueryRow(`
		SELECT id, task_id, user_id, text, filename, original_name, created_at
		FROM task_comments WHERE id = $1`, id).
		Scan(&c.ID, &c.TaskID, &c.UserID, &c.Text, &fn, &on, &c.CreatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	c.Filename = ns(fn)
	c.OriginalName = ns(on)
	return c, nil
}

func (r *TaskRepo) DeleteComment(id int) error {
	_, err := r.db.Exec(`DELETE FROM task_comments WHERE id = $1`, id)
	return err
}
