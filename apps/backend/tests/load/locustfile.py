from __future__ import annotations
import uuid
from locust import HttpUser, between, task
PASSWORD = 'Str0ng!Pass#2024'

class TicketBuyer(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        self.email = f'load_{uuid.uuid4().hex[:8]}@test.com'
        self.user_id = ''
        self.access_token = ''
        self.refresh_token = ''
        self.show_id = ''
        r = self.client.post('/v1/auth/signup', json={'email': self.email, 'password': PASSWORD})
        if r.status_code == 201:
            self.user_id = r.json().get('user_id', '')
        r = self.client.post('/v1/auth/login', json={'email': self.email, 'password': PASSWORD})
        if r.status_code == 200:
            self.access_token = r.json().get('access_token', '')
            self.refresh_token = r.json().get('refresh_token', '')
        r = self.client.get('/v1/events')
        if r.status_code == 200:
            events = r.json()
            if events:
                event_id = events[0].get('event_id', '')
                if event_id:
                    r2 = self.client.get(f'/v1/events/{event_id}/showtimes')
                    if r2.status_code == 200:
                        showtimes = r2.json()
                        if showtimes:
                            self.show_id = showtimes[0].get('show_id', '')

    def _auth_headers(self) -> dict[str, str]:
        return {'Authorization': f'Bearer {self.access_token}'} if self.access_token else {}

    @task(5)
    def join_queue(self) -> None:
        if not self.access_token or not self.show_id:
            return
        self.client.post('/v1/queue/join', json={'show_id': self.show_id}, headers=self._auth_headers(), name='/v1/queue/join')

    @task(3)
    def check_queue_status(self) -> None:
        if not self.access_token or not self.show_id:
            return
        self.client.get(f'/v1/queue/status?show_id={self.show_id}', headers=self._auth_headers(), name='/v1/queue/status')

    @task(2)
    def check_catalog(self) -> None:
        self.client.get('/v1/venues', name='/v1/venues')
        self.client.get('/v1/events', name='/v1/events')

    @task(1)
    def list_bookings(self) -> None:
        if not self.access_token:
            return
        self.client.get('/v1/bookings', headers=self._auth_headers(), name='/v1/bookings')

    @task(1)
    def health_check(self) -> None:
        self.client.get('/health', name='/health')
