package app

import (
	"net/http"
	"strings"

	"github.com/B216-lab/backend/internal/httpapi"
)

func NewServer(handler *httpapi.Handler, allowedOrigins []string, port string) *http.Server {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", handler.Healthz)
	mux.HandleFunc("/api/v1/public/forms/movements", handler.SubmitMovementsForm)
	mux.HandleFunc("/v1/public/forms/movements", handler.SubmitMovementsForm)

	return &http.Server{
		Addr:    ":" + port,
		Handler: withCORS(mux, allowedOrigins),
	}
}

func withCORS(next http.Handler, allowedOrigins []string) http.Handler {
	allowedSet := make(map[string]struct{}, len(allowedOrigins))
	allowAny := false
	for _, origin := range allowedOrigins {
		if origin == "*" {
			allowAny = true
			continue
		}
		allowedSet[strings.TrimSpace(origin)] = struct{}{}
	}

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := strings.TrimSpace(r.Header.Get("Origin"))
		if origin != "" {
			if allowAny {
				w.Header().Set("Access-Control-Allow-Origin", "*")
			} else if _, ok := allowedSet[origin]; ok {
				w.Header().Set("Access-Control-Allow-Origin", origin)
				w.Header().Add("Vary", "Origin")
			}
			w.Header().Set("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		}

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		next.ServeHTTP(w, r)
	})
}
