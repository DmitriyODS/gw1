package handler

import (
	"os"
	"path/filepath"

	"github.com/gofiber/fiber/v2"
)

type FileHandler struct {
	uploadDir string
}

func NewFileHandler(uploadDir string) *FileHandler {
	return &FileHandler{uploadDir: uploadDir}
}

// ServeUpload serves a file from the uploads directory.
func (h *FileHandler) ServeUpload(c *fiber.Ctx) error {
	name := filepath.Base(c.Params("filename")) // sanitize
	path := filepath.Join(h.uploadDir, name)
	if _, err := os.Stat(path); os.IsNotExist(err) {
		return fiber.ErrNotFound
	}
	return c.SendFile(path)
}
