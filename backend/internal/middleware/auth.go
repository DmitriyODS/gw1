package middleware

import (
	"strings"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/golang-jwt/jwt/v5"
	"gw1/backend/internal/domain"
)

type Claims struct {
	UserID int         `json:"user_id"`
	Role   domain.Role `json:"role"`
	jwt.RegisteredClaims
}

func NewAccessToken(userID int, role domain.Role, secret string) (string, error) {
	claims := Claims{
		UserID: userID,
		Role:   role,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
		},
	}
	return jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString([]byte(secret))
}

func NewRefreshToken(userID int, role domain.Role, secret string) (string, error) {
	claims := Claims{
		UserID: userID,
		Role:   role,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(7 * 24 * time.Hour)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
		},
	}
	return jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString([]byte(secret))
}

func ParseToken(tokenStr, secret string) (*Claims, error) {
	tok, err := jwt.ParseWithClaims(tokenStr, &Claims{}, func(t *jwt.Token) (interface{}, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fiber.ErrUnauthorized
		}
		return []byte(secret), nil
	})
	if err != nil {
		return nil, err
	}
	if claims, ok := tok.Claims.(*Claims); ok && tok.Valid {
		return claims, nil
	}
	return nil, fiber.ErrUnauthorized
}

// Protected returns middleware that validates Bearer JWT and injects claims into context.
func Protected(secret string) fiber.Handler {
	return func(c *fiber.Ctx) error {
		header := c.Get("Authorization")
		if !strings.HasPrefix(header, "Bearer ") {
			return fiber.ErrUnauthorized
		}
		claims, err := ParseToken(strings.TrimPrefix(header, "Bearer "), secret)
		if err != nil {
			return fiber.ErrUnauthorized
		}
		c.Locals("claims", claims)
		return c.Next()
	}
}

// RequireRole returns middleware that checks the minimum role.
func RequireManager(c *fiber.Ctx) error {
	return requireRole(c, func(r domain.Role) bool { return r.CanManage() })
}

func RequireAdmin(c *fiber.Ctx) error {
	return requireRole(c, func(r domain.Role) bool { return r.CanAdmin() })
}

func RequireSuperAdmin(c *fiber.Ctx) error {
	return requireRole(c, func(r domain.Role) bool { return r.IsSuperAdmin() })
}

func requireRole(c *fiber.Ctx, check func(domain.Role) bool) error {
	claims := GetClaims(c)
	if claims == nil || !check(claims.Role) {
		return fiber.ErrForbidden
	}
	return c.Next()
}

func GetClaims(c *fiber.Ctx) *Claims {
	v := c.Locals("claims")
	if v == nil {
		return nil
	}
	cl, _ := v.(*Claims)
	return cl
}
