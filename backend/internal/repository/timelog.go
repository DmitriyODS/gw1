package repository

import (
	"database/sql"
	"errors"

	"gw1/backend/internal/domain"
)

type TimeLogRepo struct {
	db *sql.DB
}

func NewTimeLogRepo(db *sql.DB) *TimeLogRepo {
	return &TimeLogRepo{db: db}
}

func (r *TimeLogRepo) FindActive(userID int) (*domain.TimeLog, error) {
	tl := &domain.TimeLog{}
	err := r.db.QueryRow(`
		SELECT id, task_id, user_id, started_at, ended_at
		FROM time_logs
		WHERE user_id = $1 AND ended_at IS NULL
		LIMIT 1`, userID).
		Scan(&tl.ID, &tl.TaskID, &tl.UserID, &tl.StartedAt, &tl.EndedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return tl, err
}

func (r *TimeLogRepo) FindByTask(taskID int) ([]domain.TimeLog, error) {
	rows, err := r.db.Query(`
		SELECT tl.id, tl.task_id, tl.user_id, tl.started_at, tl.ended_at,
		       u.id, u.username, u.full_name
		FROM time_logs tl
		JOIN users u ON u.id = tl.user_id
		WHERE tl.task_id = $1
		ORDER BY tl.started_at`, taskID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var logs []domain.TimeLog
	for rows.Next() {
		var tl domain.TimeLog
		var endedAt sql.NullTime
		u := &domain.User{}
		if err := rows.Scan(
			&tl.ID, &tl.TaskID, &tl.UserID, &tl.StartedAt, &endedAt,
			&u.ID, &u.Username, &u.FullName,
		); err != nil {
			return nil, err
		}
		tl.EndedAt = nt(endedAt)
		tl.User = u
		logs = append(logs, tl)
	}
	return logs, rows.Err()
}

func (r *TimeLogRepo) Start(taskID, userID int) (*domain.TimeLog, error) {
	tl := &domain.TimeLog{}
	err := r.db.QueryRow(`
		INSERT INTO time_logs (task_id, user_id)
		VALUES ($1, $2)
		RETURNING id, task_id, user_id, started_at, ended_at`,
		taskID, userID,
	).Scan(&tl.ID, &tl.TaskID, &tl.UserID, &tl.StartedAt, &tl.EndedAt)
	return tl, err
}

func (r *TimeLogRepo) Stop(id int) error {
	_, err := r.db.Exec(`UPDATE time_logs SET ended_at = NOW() WHERE id = $1`, id)
	return err
}

func (r *TimeLogRepo) StopAllByUser(userID int) error {
	_, err := r.db.Exec(
		`UPDATE time_logs SET ended_at = NOW() WHERE user_id = $1 AND ended_at IS NULL`, userID)
	return err
}
