from __future__ import annotations

from django.urls import path

from .views import MachineListCreateView, MachineStopView, MachineExtendView

app_name = "machines"

# 路由：靶机列表、启动、停止
urlpatterns = [
    path("", MachineListCreateView.as_view(), name="list-create"),
    path("<int:machine_id>/stop/", MachineStopView.as_view(), name="stop"),
    path("<int:machine_id>/extend/", MachineExtendView.as_view(), name="extend"),
]
