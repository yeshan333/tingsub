package desktop

import "context"

// Service exposes only the capabilities of the bundled desktop page. Lifecycle
// and menu operations stay private and cannot be invoked through MyGo bindings.
type Service struct{ worker *Worker }

func NewService(worker *Worker) *Service { return &Service{worker: worker} }

func (s *Service) Snapshot(ctx context.Context) (any, error) {
	return s.worker.Call(ctx, "snapshot")
}
func (s *Service) StartService(ctx context.Context) (any, error) {
	return s.worker.Call(ctx, "start_service")
}
func (s *Service) StopService(ctx context.Context) (any, error) {
	return s.worker.Call(ctx, "stop_service")
}
func (s *Service) PrepareModels(ctx context.Context, selection, download map[string]any) (any, error) {
	return s.worker.Call(ctx, "prepare_models", selection, download)
}
func (s *Service) SavePreferences(ctx context.Context, patch map[string]any) (any, error) {
	return s.worker.Call(ctx, "save_preferences", patch)
}
func (s *Service) GetInterface(ctx context.Context) (any, error) {
	return s.worker.Call(ctx, "get_interface")
}
func (s *Service) SaveInterface(ctx context.Context, value map[string]any) (any, error) {
	return s.worker.Call(ctx, "save_interface", value)
}
func (s *Service) CopyPairing(ctx context.Context) (any, error) {
	return s.worker.Call(ctx, "copy_pairing")
}
func (s *Service) OpenResource(ctx context.Context, name string) (any, error) {
	return s.worker.Call(ctx, "open_resource", name)
}
