package router

import (
	"database/sql"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"
	"gw1/backend/internal/config"
	"gw1/backend/internal/domain"
	"gw1/backend/internal/handler"
	"gw1/backend/internal/middleware"
	"gw1/backend/internal/repository"
)

func New(cfg *config.Config, db *sql.DB) *fiber.App {
	app := fiber.New(fiber.Config{
		ErrorHandler: func(c *fiber.Ctx, err error) error {
			code := fiber.StatusInternalServerError
			msg := err.Error()
			if e, ok := err.(*fiber.Error); ok {
				code = e.Code
				msg = e.Message
			}
			return c.Status(code).JSON(fiber.Map{"error": msg})
		},
	})

	app.Use(recover.New())
	app.Use(logger.New())
	app.Use(cors.New(cors.Config{
		AllowOrigins:     "*",
		AllowHeaders:     "Origin, Content-Type, Accept, Authorization",
		AllowMethods:     "GET, POST, PUT, PATCH, DELETE, OPTIONS",
		AllowCredentials: false,
	}))

	// -- Repositories --
	userRepo  := repository.NewUserRepo(db)
	taskRepo  := repository.NewTaskRepo(db)
	deptRepo  := repository.NewDepartmentRepo(db)
	tlRepo    := repository.NewTimeLogRepo(db)
	rhythmRepo := repository.NewRhythmRepo(db)
	planRepo  := repository.NewPlanRepo(db)

	// -- Handlers --
	authH    := handler.NewAuthHandler(userRepo, db, cfg.JWTSecret)
	taskH    := handler.NewTaskHandler(taskRepo, tlRepo, cfg.UploadDir)
	userH    := handler.NewUserHandler(userRepo)
	deptH    := handler.NewDepartmentHandler(deptRepo)
	analytH  := handler.NewAnalyticsHandler(db)
	rhythmH  := handler.NewRhythmHandler(rhythmRepo, taskRepo)
	planH    := handler.NewPlanHandler(planRepo, taskRepo)
	mediaH   := handler.NewMediaPlanHandler(db)
	profileH := handler.NewProfileHandler(userRepo, db, cfg.AvatarDir)
	publicH  := handler.NewPublicHandler(taskRepo, deptRepo, db, cfg.UploadDir)
	adminH   := handler.NewAdminHandler(db)
	fileH    := handler.NewFileHandler(cfg.UploadDir)

	auth := middleware.Protected(cfg.JWTSecret)

	// ================================================================
	// Public routes (no auth)
	// ================================================================
	pub := app.Group("/public")
	pub.Post("/submit", publicH.Submit)
	pub.Get("/departments", publicH.Departments)
	pub.Get("/task-types", publicH.TaskTypes)

	// ================================================================
	// Auth routes
	// ================================================================
	a := app.Group("/api/auth")
	a.Post("/login", authH.Login)
	a.Post("/refresh", authH.Refresh)
	a.Post("/logout", authH.Logout)

	// ================================================================
	// Protected routes
	// ================================================================
	api := app.Group("/api", auth)

	// -- Files --
	app.Get("/uploads/:filename", auth, fileH.ServeUpload)
	app.Get("/avatars/:user_id", profileH.GetAvatar) // avatar: no auth (public access for UI)

	// -- Profile --
	api.Get("/profile", profileH.Get)
	api.Put("/profile", profileH.Update)
	api.Post("/profile/avatar", profileH.UploadAvatar)

	// -- Task types (all 19 for internal users) --
	api.Get("/task-types", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"data": domain.AllTaskTypes()})
	})

	// -- Tasks --
	t := api.Group("/tasks")
	t.Get("/", taskH.List)
	t.Post("/", taskH.Create)
	t.Get("/my-timer", taskH.MyTimer)
	t.Get("/:id", taskH.Get)
	t.Put("/:id", taskH.Update)
	t.Delete("/:id", middleware.RequireAdmin, taskH.Delete)
	t.Post("/:id/move", taskH.Move)
	t.Post("/:id/timer/start", taskH.TimerStart)
	t.Post("/:id/timer/force-start", taskH.TimerForceStart)
	t.Post("/:id/timer/pause", taskH.TimerPause)
	t.Post("/:id/done", taskH.Done)
	t.Post("/:id/delegate", middleware.RequireAdmin, taskH.Delegate)
	t.Post("/:id/unassign", middleware.RequireAdmin, taskH.Unassign)
	t.Post("/:id/attachments", taskH.UploadAttachment)
	t.Delete("/:id/attachments/:att_id", taskH.DeleteAttachment)
	t.Get("/:id/attachments/zip", taskH.DownloadZip)
	t.Post("/:id/comments", taskH.AddComment)
	t.Delete("/:id/comments/:comment_id", taskH.DeleteComment)

	// -- Users (admin+) --
	u := api.Group("/users", middleware.RequireAdmin)
	u.Get("/", userH.List)
	u.Post("/", userH.Create)
	u.Get("/:id", userH.Get)
	u.Put("/:id", userH.Update)
	u.Delete("/:id", middleware.RequireSuperAdmin, userH.Delete)

	// -- Departments --
	d := api.Group("/departments")
	d.Get("/", deptH.List)
	d.Post("/", middleware.RequireAdmin, deptH.Create)
	d.Put("/:id", middleware.RequireAdmin, deptH.Update)
	d.Delete("/:id", middleware.RequireAdmin, deptH.Delete)

	// -- Analytics --
	an := api.Group("/analytics")
	an.Get("/", analytH.Dashboard)
	an.Get("/time", analytH.TimeReport)
	an.Get("/tv", analytH.TV)
	an.Get("/export/excel", analytH.ExportExcel)

	// -- Rhythms (manager+) --
	rh := api.Group("/rhythms", middleware.RequireManager)
	rh.Get("/", rhythmH.List)
	rh.Post("/", rhythmH.Create)
	rh.Put("/:id", rhythmH.Update)
	rh.Delete("/:id", rhythmH.Delete)
	rh.Post("/:id/toggle", rhythmH.Toggle)
	rh.Post("/:id/run", rhythmH.Run)

	// -- Plans (manager+) --
	pl := api.Group("/plans", middleware.RequireManager)
	pl.Get("/", planH.List)
	pl.Post("/", planH.Create)
	pl.Put("/:id", planH.Update)
	pl.Delete("/:id", planH.Delete)
	pl.Post("/:id/push", planH.Push)
	pl.Post("/convert-due", planH.ConvertDue)

	// -- Plan groups --
	pg := api.Group("/plan-groups", middleware.RequireManager)
	pg.Get("/", planH.ListGroups)
	pg.Post("/", planH.CreateGroup)
	pg.Delete("/:id", planH.DeleteGroup)

	// -- Media plan --
	mp := api.Group("/media-plan")
	mp.Get("/", mediaH.Calendar)
	mp.Get("/export", mediaH.ExportExcel)

	// -- Admin --
	adm := api.Group("/admin", middleware.RequireAdmin)
	adm.Get("/archive", adminH.ArchiveStats)
	adm.Post("/archive/migrate-review", middleware.RequireManager, adminH.MigrateReview)
	adm.Post("/archive/run", middleware.RequireManager, adminH.ArchiveOld)
	adm.Get("/archive/preview", adminH.Preview)
	adm.Post("/archive/export", adminH.Export)
	adm.Post("/archive/import", middleware.RequireSuperAdmin, adminH.Import)

	return app
}
