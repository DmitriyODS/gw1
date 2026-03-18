package repository

import (
	"database/sql"
	"errors"
	"strconv"

	"gw1/backend/internal/domain"
)

var ErrNotFound = errors.New("not found")

type UserRepo struct {
	db *sql.DB
}

func NewUserRepo(db *sql.DB) *UserRepo {
	return &UserRepo{db: db}
}

type CreateUserInput struct {
	Username     string
	Email        *string
	PasswordHash string
	FullName     string
	Role         domain.Role
}

type UpdateUserInput struct {
	Username  *string
	Email     *string
	FullName  *string
	Role      *domain.Role
	IsActive  *bool
	AvatarPath *string
}

func (r *UserRepo) FindByID(id int) (*domain.User, error) {
	u := &domain.User{}
	var email, avatarPath sql.NullString
	err := r.db.QueryRow(`
		SELECT id, username, email, full_name, role, is_active, created_at, avatar_path
		FROM users WHERE id = $1`, id).Scan(
		&u.ID, &u.Username, &email, &u.FullName,
		&u.Role, &u.IsActive, &u.CreatedAt, &avatarPath,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	u.Email = ns(email)
	u.AvatarPath = ns(avatarPath)
	return u, nil
}

type userWithHash struct {
	User         domain.User
	PasswordHash string
}

func (r *UserRepo) FindByUsername(username string) (*domain.User, string, error) {
	u := &domain.User{}
	var email, avatarPath sql.NullString
	var hash string
	err := r.db.QueryRow(`
		SELECT id, username, email, full_name, role, is_active, created_at, avatar_path, password_hash
		FROM users WHERE username = $1`, username).Scan(
		&u.ID, &u.Username, &email, &u.FullName,
		&u.Role, &u.IsActive, &u.CreatedAt, &avatarPath, &hash,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, "", ErrNotFound
	}
	if err != nil {
		return nil, "", err
	}
	u.Email = ns(email)
	u.AvatarPath = ns(avatarPath)
	return u, hash, nil
}

func (r *UserRepo) FindAll(activeOnly bool) ([]domain.User, error) {
	q := `SELECT id, username, email, full_name, role, is_active, created_at, avatar_path FROM users`
	if activeOnly {
		q += ` WHERE is_active = true`
	}
	q += ` ORDER BY full_name`

	rows, err := r.db.Query(q)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var users []domain.User
	for rows.Next() {
		var u domain.User
		var email, avatarPath sql.NullString
		if err := rows.Scan(&u.ID, &u.Username, &email, &u.FullName,
			&u.Role, &u.IsActive, &u.CreatedAt, &avatarPath); err != nil {
			return nil, err
		}
		u.Email = ns(email)
		u.AvatarPath = ns(avatarPath)
		users = append(users, u)
	}
	return users, rows.Err()
}

func (r *UserRepo) Create(inp *CreateUserInput) (*domain.User, error) {
	u := &domain.User{}
	var email, avatarPath sql.NullString
	err := r.db.QueryRow(`
		INSERT INTO users (username, email, password_hash, full_name, role)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, username, email, full_name, role, is_active, created_at, avatar_path`,
		inp.Username, inp.Email, inp.PasswordHash, inp.FullName, inp.Role,
	).Scan(&u.ID, &u.Username, &email, &u.FullName,
		&u.Role, &u.IsActive, &u.CreatedAt, &avatarPath)
	if err != nil {
		return nil, err
	}
	u.Email = ns(email)
	u.AvatarPath = ns(avatarPath)
	return u, nil
}

func (r *UserRepo) Update(id int, inp *UpdateUserInput) (*domain.User, error) {
	// Build dynamic update
	set := `updated_at = NOW()`
	args := []interface{}{id}
	i := 2

	if inp.Username != nil {
		set += `, username = $` + itoa(i)
		args = append(args, *inp.Username)
		i++
	}
	if inp.Email != nil {
		set += `, email = $` + itoa(i)
		args = append(args, *inp.Email)
		i++
	}
	if inp.FullName != nil {
		set += `, full_name = $` + itoa(i)
		args = append(args, *inp.FullName)
		i++
	}
	if inp.Role != nil {
		set += `, role = $` + itoa(i)
		args = append(args, *inp.Role)
		i++
	}
	if inp.IsActive != nil {
		set += `, is_active = $` + itoa(i)
		args = append(args, *inp.IsActive)
		i++
	}
	if inp.AvatarPath != nil {
		set += `, avatar_path = $` + itoa(i)
		args = append(args, *inp.AvatarPath)
		i++
	}

	u := &domain.User{}
	var email, avatarPath sql.NullString
	err := r.db.QueryRow(`
		UPDATE users SET `+set+`
		WHERE id = $1
		RETURNING id, username, email, full_name, role, is_active, created_at, avatar_path`,
		args...,
	).Scan(&u.ID, &u.Username, &email, &u.FullName,
		&u.Role, &u.IsActive, &u.CreatedAt, &avatarPath)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	u.Email = ns(email)
	u.AvatarPath = ns(avatarPath)
	return u, nil
}

func (r *UserRepo) UpdatePassword(id int, hash string) error {
	_, err := r.db.Exec(`UPDATE users SET password_hash = $1 WHERE id = $2`, hash, id)
	return err
}

func (r *UserRepo) Delete(id int) error {
	res, err := r.db.Exec(`DELETE FROM users WHERE id = $1`, id)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrNotFound
	}
	return nil
}

func itoa(i int) string {
	return strconv.Itoa(i)
}
