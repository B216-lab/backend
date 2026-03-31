package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/B216-lab/backend/internal/app"
	"github.com/B216-lab/backend/internal/config"
	"github.com/B216-lab/backend/internal/forms"
	"github.com/B216-lab/backend/internal/httpapi"
	"github.com/B216-lab/backend/internal/store/postgres"
	"github.com/jackc/pgx/v5/pgxpool"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("load config: %v", err)
	}

	ctx := context.Background()
	pool, err := pgxpool.New(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("connect to database: %v", err)
	}
	defer pool.Close()

	repo := postgres.NewRepository(pool)
	service := forms.NewService(repo)
	handler := httpapi.NewHandler(service, cfg.MaxBodyBytes)
	server := app.NewServer(handler, cfg.CORSAllowedOrigins, cfg.ServerPort)

	go func() {
		log.Printf("listening on %s", server.Addr)
		if serveErr := server.ListenAndServe(); serveErr != nil && !errors.Is(serveErr, http.ErrServerClosed) {
			log.Fatalf("start server: %v", serveErr)
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	if err = server.Shutdown(shutdownCtx); err != nil {
		log.Fatalf("shutdown server: %v", err)
	}
}
