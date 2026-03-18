package repository

import (
	"database/sql"
	"time"
)

func ns(s sql.NullString) *string {
	if !s.Valid {
		return nil
	}
	return &s.String
}

func ni(i sql.NullInt64) *int {
	if !i.Valid {
		return nil
	}
	v := int(i.Int64)
	return &v
}

func nt(t sql.NullTime) *time.Time {
	if !t.Valid {
		return nil
	}
	return &t.Time
}
