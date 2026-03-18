package repository

import (
	"database/sql"
	"errors"

	"gw1/backend/internal/domain"
)

type DepartmentRepo struct {
	db *sql.DB
}

func NewDepartmentRepo(db *sql.DB) *DepartmentRepo {
	return &DepartmentRepo{db: db}
}

func (r *DepartmentRepo) FindAll(activeOnly bool) ([]domain.Department, error) {
	q := `SELECT id, name, is_active FROM departments`
	if activeOnly {
		q += ` WHERE is_active = true`
	}
	q += ` ORDER BY name`

	rows, err := r.db.Query(q)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var depts []domain.Department
	for rows.Next() {
		var d domain.Department
		if err := rows.Scan(&d.ID, &d.Name, &d.IsActive); err != nil {
			return nil, err
		}
		depts = append(depts, d)
	}
	return depts, rows.Err()
}

func (r *DepartmentRepo) FindByID(id int) (*domain.Department, error) {
	d := &domain.Department{}
	err := r.db.QueryRow(`SELECT id, name, is_active FROM departments WHERE id = $1`, id).
		Scan(&d.ID, &d.Name, &d.IsActive)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return d, err
}

func (r *DepartmentRepo) Create(name string) (*domain.Department, error) {
	d := &domain.Department{}
	err := r.db.QueryRow(
		`INSERT INTO departments (name) VALUES ($1) RETURNING id, name, is_active`, name,
	).Scan(&d.ID, &d.Name, &d.IsActive)
	return d, err
}

func (r *DepartmentRepo) Update(id int, name string, isActive *bool) (*domain.Department, error) {
	var d domain.Department
	if isActive != nil {
		err := r.db.QueryRow(
			`UPDATE departments SET name = $1, is_active = $2 WHERE id = $3 RETURNING id, name, is_active`,
			name, *isActive, id,
		).Scan(&d.ID, &d.Name, &d.IsActive)
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrNotFound
		}
		return &d, err
	}
	err := r.db.QueryRow(
		`UPDATE departments SET name = $1 WHERE id = $2 RETURNING id, name, is_active`,
		name, id,
	).Scan(&d.ID, &d.Name, &d.IsActive)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return &d, err
}

func (r *DepartmentRepo) Delete(id int) error {
	res, err := r.db.Exec(`DELETE FROM departments WHERE id = $1`, id)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrNotFound
	}
	return nil
}
