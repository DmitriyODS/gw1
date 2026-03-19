package domain

import "time"

// ----------------------------------------------------------------
// Role
// ----------------------------------------------------------------

type Role string

const (
	RoleSuperAdmin Role = "super_admin"
	RoleManager    Role = "manager"
	RoleAdmin      Role = "admin"
	RoleStaff      Role = "staff"
	RoleTV         Role = "tv"
)

func (r Role) CanManage() bool {
	return r == RoleSuperAdmin || r == RoleManager
}

func (r Role) CanAdmin() bool {
	return r == RoleSuperAdmin || r == RoleManager || r == RoleAdmin
}

func (r Role) IsSuperAdmin() bool { return r == RoleSuperAdmin }
func (r Role) IsTV() bool          { return r == RoleTV }

// ----------------------------------------------------------------
// TaskStatus
// ----------------------------------------------------------------

type TaskStatus string

const (
	StatusNew        TaskStatus = "new"
	StatusInProgress TaskStatus = "in_progress"
	StatusPaused     TaskStatus = "paused"
	StatusDone       TaskStatus = "done"
)

// ----------------------------------------------------------------
// Urgency
// ----------------------------------------------------------------

type Urgency string

const (
	UrgencySlow      Urgency = "slow"
	UrgencyNormal    Urgency = "normal"
	UrgencyImportant Urgency = "important"
	UrgencyUrgent    Urgency = "urgent"
)

// ----------------------------------------------------------------
// Task types
// ----------------------------------------------------------------

type TaskTypeInfo struct {
	Value      string `json:"value"`
	Label      string `json:"label"`
	IsExternal bool   `json:"is_external"`
}

// ExternalTaskTypes — 13 типов доступных во внешней форме.
var ExternalTaskTypes = []TaskTypeInfo{
	{"publication", "Публикация", true},
	{"design_image", "Разработка картинки", true},
	{"design_handout", "Разработка раздатки", true},
	{"design_banner", "Разработка баннера", true},
	{"design_poster", "Разработка плаката/афиши", true},
	{"verify_presentation", "Верификация презентации", true},
	{"design_presentation", "Разработка презентации", true},
	{"verify_design", "Верификация дизайна", true},
	{"design_merch", "Разработка сувенирной продукции", true},
	{"design_cards", "Разработка открыток", true},
	{"mailing", "Выполнение корпоративных рассылок", true},
	{"photo_video", "Фото/видео сопровождение", true},
	{"other", "Другое", true},
}

// InternalTaskTypes — 6 типов только для внутренних пользователей.
var InternalTaskTypes = []TaskTypeInfo{
	{"mail_check", "Проверка почты", false},
	{"edits", "Правки по задаче", false},
	{"video_edit", "Монтаж видео", false},
	{"photo_edit", "Обработка фото", false},
	{"internal_work", "Внутренняя работа отдела", false},
	{"external_work", "Внешняя работа отдела", false},
}

// AllTaskTypes returns all 19 task types.
func AllTaskTypes() []TaskTypeInfo {
	all := make([]TaskTypeInfo, 0, len(ExternalTaskTypes)+len(InternalTaskTypes))
	all = append(all, ExternalTaskTypes...)
	all = append(all, InternalTaskTypes...)
	return all
}

// ----------------------------------------------------------------
// Frequency
// ----------------------------------------------------------------

type Frequency string

const (
	FrequencyDaily   Frequency = "daily"
	FrequencyWeekly  Frequency = "weekly"
	FrequencyMonthly Frequency = "monthly"
)

// ----------------------------------------------------------------
// Domain models
// ----------------------------------------------------------------

type User struct {
	ID           int       `json:"id"`
	Username     string    `json:"username"`
	Email        *string   `json:"email,omitempty"`
	FullName     string    `json:"full_name"`
	Role         Role      `json:"role"`
	IsActive     bool      `json:"is_active"`
	CreatedAt    time.Time `json:"created_at"`
	AvatarPath   *string   `json:"avatar_path,omitempty"`
}

type Department struct {
	ID       int    `json:"id"`
	Name     string `json:"name"`
	IsActive bool   `json:"is_active"`
}

type Task struct {
	ID            int                    `json:"id"`
	Title         string                 `json:"title"`
	Description   string                 `json:"description"`
	Status        TaskStatus             `json:"status"`
	Urgency       Urgency                `json:"urgency"`
	TaskType      *string                `json:"task_type,omitempty"`
	Tags          []string               `json:"tags"`
	DynamicFields map[string]interface{} `json:"dynamic_fields"`
	CustomerName  *string                `json:"customer_name,omitempty"`
	CustomerPhone *string                `json:"customer_phone,omitempty"`
	CustomerEmail *string                `json:"customer_email,omitempty"`
	Deadline      *time.Time             `json:"deadline,omitempty"`
	CreatedAt     time.Time              `json:"created_at"`
	CompletedAt   *time.Time             `json:"completed_at,omitempty"`
	DepartmentID  *int                   `json:"department_id,omitempty"`
	CreatedByID   int                    `json:"created_by_id"`
	AssignedToID  *int                   `json:"assigned_to_id,omitempty"`
	ParentTaskID  *int                   `json:"parent_task_id,omitempty"`
	IsArchived    bool                   `json:"is_archived"`
	ArchivedAt    *time.Time             `json:"archived_at,omitempty"`
	// Nested (populated on demand)
	Department  *Department      `json:"department,omitempty"`
	CreatedBy   *User            `json:"created_by,omitempty"`
	AssignedTo  *User            `json:"assigned_to,omitempty"`
	Attachments []TaskAttachment `json:"attachments,omitempty"`
	TimeLogs    []TimeLog        `json:"time_logs,omitempty"`
	Comments    []TaskComment    `json:"comments,omitempty"`
	Subtasks    []Task           `json:"subtasks,omitempty"`
}

type TaskAttachment struct {
	ID           int       `json:"id"`
	TaskID       int       `json:"task_id"`
	Filename     string    `json:"filename"`
	OriginalName string    `json:"original_name"`
	UploadedAt   time.Time `json:"uploaded_at"`
}

type TaskComment struct {
	ID           int       `json:"id"`
	TaskID       int       `json:"task_id"`
	UserID       int       `json:"user_id"`
	Text         string    `json:"text"`
	Filename     *string   `json:"filename,omitempty"`
	OriginalName *string   `json:"original_name,omitempty"`
	CreatedAt    time.Time `json:"created_at"`
	User         *User     `json:"user,omitempty"`
}

type TimeLog struct {
	ID        int        `json:"id"`
	TaskID    int        `json:"task_id"`
	UserID    int        `json:"user_id"`
	StartedAt time.Time  `json:"started_at"`
	EndedAt   *time.Time `json:"ended_at,omitempty"`
	User      *User      `json:"user,omitempty"`
}

type Rhythm struct {
	ID              int        `json:"id"`
	Name            string     `json:"name"`
	Description     string     `json:"description"`
	Frequency       Frequency  `json:"frequency"`
	DayOfWeek       *int       `json:"day_of_week,omitempty"`
	DayOfMonth      *int       `json:"day_of_month,omitempty"`
	TaskTitle       string     `json:"task_title"`
	TaskDescription string     `json:"task_description"`
	TaskUrgency     Urgency    `json:"task_urgency"`
	TaskType        *string    `json:"task_type,omitempty"`
	TaskTags        []string   `json:"task_tags"`
	DepartmentID    *int       `json:"department_id,omitempty"`
	CreatedByID     int        `json:"created_by_id"`
	IsActive        bool       `json:"is_active"`
	LastRunAt       *time.Time `json:"last_run_at,omitempty"`
	CreatedAt       time.Time  `json:"created_at"`
	Department      *Department `json:"department,omitempty"`
}

type PlanGroup struct {
	ID          int       `json:"id"`
	Name        string    `json:"name"`
	CreatedByID int       `json:"created_by_id"`
	CreatedAt   time.Time `json:"created_at"`
}

type Plan struct {
	ID              int                    `json:"id"`
	Title           string                 `json:"title"`
	Description     string                 `json:"description"`
	CustomerName    *string                `json:"customer_name,omitempty"`
	CustomerPhone   *string                `json:"customer_phone,omitempty"`
	CustomerEmail   *string                `json:"customer_email,omitempty"`
	ReleaseDate     *time.Time             `json:"release_date,omitempty"`
	TaskType        *string                `json:"task_type,omitempty"`
	Urgency         Urgency                `json:"urgency"`
	Tags            []string               `json:"tags"`
	DynamicFields   map[string]interface{} `json:"dynamic_fields"`
	GroupID         *int                   `json:"group_id,omitempty"`
	DepartmentID    *int                   `json:"department_id,omitempty"`
	CreatedByID     int                    `json:"created_by_id"`
	IsConverted     bool                   `json:"is_converted"`
	ConvertedTaskID *int                   `json:"converted_task_id,omitempty"`
	CreatedAt       time.Time              `json:"created_at"`
	Department      *Department            `json:"department,omitempty"`
	Group           *PlanGroup             `json:"group,omitempty"`
}
