package config

import (
	"errors"
	"os"
	"strconv"
	"strings"
)

type Config struct {
	ServerPort         string
	DatabaseURL        string
	CORSAllowedOrigins []string
	MaxBodyBytes       int64
}

func Load() (Config, error) {
	cfg := Config{
		ServerPort:         getenvDefault("SERVER_PORT", "8081"),
		DatabaseURL:        strings.TrimSpace(os.Getenv("DATABASE_URL")),
		CORSAllowedOrigins: splitCSV(getenvDefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://frontend:5173,http://frontend:80")),
		MaxBodyBytes:       int64(getenvIntDefault("MAX_BODY_BYTES", 1_048_576)),
	}

	if cfg.DatabaseURL == "" {
		return Config{}, errors.New("DATABASE_URL is required")
	}
	return cfg, nil
}

func getenvDefault(key string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func getenvIntDefault(key string, fallback int) int {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(raw)
	if err != nil {
		return fallback
	}
	return parsed
}

func splitCSV(raw string) []string {
	parts := strings.Split(raw, ",")
	out := make([]string, 0, len(parts))
	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed == "" {
			continue
		}
		out = append(out, trimmed)
	}
	return out
}
