package main

import (
	"database/sql"
	"flag"
	"fmt"
	"log"
	"os"

	"golang.org/x/crypto/bcrypt"
	"gw1/backend/internal/config"
	"gw1/backend/internal/db"
	"gw1/backend/internal/router"
)

func main() {
	migrateFlag := flag.Bool("migrate", false, "run SQL migrations and exit")
	seedFlag    := flag.Bool("seed", false, "create initial super_admin and seed departments")
	flag.Parse()

	cfg := config.Load()

	database, err := db.Connect(cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("db connect: %v", err)
	}
	defer database.Close()

	if *migrateFlag {
		if err := db.Migrate(database, "migrations"); err != nil {
			log.Fatalf("migrate: %v", err)
		}
		log.Println("migrations applied successfully")
		return
	}

	if *seedFlag {
		if err := seed(database); err != nil {
			log.Fatalf("seed: %v", err)
		}
		return
	}

	for _, dir := range []string{cfg.UploadDir, cfg.AvatarDir} {
		if err := os.MkdirAll(dir, 0755); err != nil {
			log.Fatalf("mkdir %s: %v", dir, err)
		}
	}

	app := router.New(cfg, database)
	log.Printf("server listening on :%s", cfg.Port)
	log.Fatal(app.Listen(":" + cfg.Port))
}

func seed(d *sql.DB) error {
	var count int
	d.QueryRow(`SELECT COUNT(*) FROM users WHERE username = 'admin'`).Scan(&count)
	if count > 0 {
		fmt.Println("admin user already exists, skipping user seed")
	} else {
		hash, err := bcrypt.GenerateFromPassword([]byte("admin123"), bcrypt.DefaultCost)
		if err != nil {
			return err
		}
		if _, err := d.Exec(`
			INSERT INTO users (username, full_name, password_hash, role)
			VALUES ('admin', 'Administrator', $1, 'super_admin')`, string(hash)); err != nil {
			return fmt.Errorf("insert admin: %w", err)
		}
		fmt.Println("created user: admin / admin123")
	}

	depts := []string{"SMM", "Дизайн", "Разработка", "Контент", "PR"}
	for _, name := range depts {
		d.Exec(`INSERT INTO departments (name) VALUES ($1) ON CONFLICT (name) DO NOTHING`, name)
	}
	fmt.Println("seeded departments:", depts)
	return nil
}
