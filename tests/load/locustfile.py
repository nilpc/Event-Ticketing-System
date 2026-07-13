"""Phase 6.4: Locust load test — simulate fans hitting /queue/join.

Run via:  locust -f tests/load/locustfile.py --host http://127.0.0.1:8000

NOTE: Minikube is for functional concurrency validation only.
True throughput benchmarking happens in EKS.
"""

from __future__ import annotations

import uuid

from locust import HttpUser, between, task


class TicketBuyer(HttpUser):
    """Simulate a fan joining the queue, checking status, and attempting checkout."""

    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        """Create a unique user account on start."""
        self.email = f"load_{uuid.uuid4().hex[:8]}@test.com"
        self.password = "Str0ng!Pass#2024"
        self.user_id = ""
        self.access_token = ""
        self.show_id = ""

        # Signup
        r = self.client.post(
            "/v1/auth/signup",
            json={"email": self.email, "password": self.password},
        )
        if r.status_code == 201:
            self.user_id = r.json().get("user_id", "")

        # Login
        r = self.client.post(
            "/v1/auth/login",
            json={"email": self.email, "password": self.password},
        )
        if r.status_code == 200:
            self.access_token = r.json().get("access_token", "")

        # Pick a showtime (assume seeded data)
        r = self.client.get("/v1/events")
        if r.status_code == 200:
            events = r.json()
            if events:
                # Use first event's showtime
                event_id = events[0].get("event_id", "")
                if event_id:
                    r2 = self.client.get(f"/v1/showtimes/{event_id}")
                    if r2.status_code == 200:
                        self.show_id = r2.json().get("show_id", "")

    @task(5)
    def join_queue(self) -> None:
        """FR-6: Join the ticket queue."""
        if not self.access_token or not self.show_id:
            return
        self.client.post(
            "/v1/queue/join",
            json={"show_id": self.show_id},
            headers={"Authorization": f"Bearer {self.access_token}"},
            name="/v1/queue/join",
        )

    @task(3)
    def check_queue_status(self) -> None:
        """FR-6: Check queue position."""
        if not self.access_token or not self.show_id:
            return
        self.client.get(
            f"/v1/queue/status?show_id={self.show_id}",
            headers={"Authorization": f"Bearer {self.access_token}"},
            name="/v1/queue/status",
        )

    @task(2)
    def check_catalog(self) -> None:
        """FR-4: Browse the catalog."""
        self.client.get("/v1/venues", name="/v1/venues")
        self.client.get("/v1/events", name="/v1/events")

    @task(1)
    def health_check(self) -> None:
        """FR-12: Liveness probe."""
        self.client.get("/health", name="/health")
