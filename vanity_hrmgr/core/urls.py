"""URLs de la API REST con viewsets y endpoint de dashboard."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from employees.views import UserViewSet, BranchViewSet, EmployeeViewSet
from requests.views import RequestViewSet, RequestCommentViewSet
from absences.views import AbsenceViewSet
from api_views import DashboardAPIView, CalendarEventsAPIView

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'branches', BranchViewSet)
router.register(r'employees', EmployeeViewSet)
router.register(r'requests', RequestViewSet)
router.register(r'absences', AbsenceViewSet)

urls = router.urls

urlpatterns = [
    path('dashboard/', DashboardAPIView.as_view(), name='api-dashboard'),
    path('dashboard/events/', CalendarEventsAPIView.as_view(), name='api-calendar-events'),
] + urls