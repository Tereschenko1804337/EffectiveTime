import logging

from datetime import datetime, time, timedelta

from adrf.requests import AsyncRequest
from adrf.viewsets import ViewSet
from asgiref.sync import sync_to_async
from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from common.models import Category
from domain.enums.status_type import StatusType
from domain.schemas.task.canban import CanbanColumnRetriveDTO
from domain.schemas.task.common import StatusRetriveDTO, SprintRetriveDTO, TagRetrieveDTO, CategoryRetriveDTO, \
    TagCreateDTO, SubtaskBulkCreateDTO, CommentCreateDTO, CommentRetrieveDTO, TaskHistoryRetrieveDTO, SubtaskCompletedUpdateDTO
from domain.schemas.task.error import TaskCreateErrorDTO
from domain.schemas.task.main import TaskCreateDTO, TaskRetrieveDTO, TaskStatusUpdateDTO, TaskTimingUpdateDTO, TaskLifecycleSegment
from infrastructure.ai.openrouter_planner import TaskInput as PlannerTaskInput, TimeSlot as PlannerTimeSlot, analyze_task
from infrastructure.comon.authetication import AsyncAuthentication
from infrastructure.comon.login_decorator import login_required
from task.models import Status, Sprint, Tag, Task, Subtask, Comment, TaskHistory


class TaskAsyncViewSet(ViewSet):
    authentication_classes = [AsyncAuthentication]

    @staticmethod
    def _format_duration(delta: timedelta) -> str:
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "< 1 мин"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} мин"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} ч {minutes % 60} мин"
        days = hours // 24
        if days < 30:
            return f"{days} дн {hours % 24} ч"
        months = days // 30
        return f"{months} мес {days % 30} дн"

    async def _calculate_lifecycle(self, task) -> tuple[list[TaskLifecycleSegment], str]:
        history = TaskHistory.objects.filter(task_id=task.id, field="Статус").order_by("created_at")
        history_items = [h async for h in history]
        
        # Get all statuses for colors
        statuses = Status.objects.all()
        status_map = {s.name: s.color async for s in statuses}
        
        segments = []
        cursor = task.created_at
        
        # Determine initial status
        current_status = "Новый" # Default fallback
        if history_items:
            current_status = history_items[0].old_value
        elif task.status:
            current_status = task.status.name
            
        now = timezone.now()
        
        # Iterate history
        for item in history_items:
            end = item.created_at
            duration = end - cursor
            
            segments.append({
                "status": current_status,
                "color": status_map.get(current_status, "#e0e0e0"),
                "duration_delta": duration,
                "start": cursor,
                "end": end
            })
            
            cursor = end
            current_status = item.new_value
            
        # Add final/current segment
        final_duration = now - cursor
        segments.append({
            "status": current_status,
            "color": status_map.get(current_status, "#e0e0e0"),
            "duration_delta": final_duration,
            "start": cursor,
            "end": now
        })
        
        # Calculate total and percentages
        total_seconds = sum([s["duration_delta"].total_seconds() for s in segments])
        total_duration_str = self._format_duration(timedelta(seconds=total_seconds))
        
        result_segments = []
        for s in segments:
            secs = s["duration_delta"].total_seconds()
            percent = (secs / total_seconds * 100) if total_seconds > 0 else 0
            result_segments.append(TaskLifecycleSegment(
                status=s["status"],
                color=s["color"],
                duration=self._format_duration(s["duration_delta"]),
                duration_seconds=int(s["duration_delta"].total_seconds()),
                percent=round(percent, 1),
                start=s["start"],
                end=s["end"]
            ))
            
        return result_segments, total_duration_str

    @staticmethod
    def _history_text(value) -> str:
        if value is None:
            return "—"
        text = str(value)
        text = text.replace("\n", " ").strip()
        if len(text) > 180:
            return text[:180] + "…"
        return text

    @staticmethod
    def _format_dt(value) -> str:
        if value is None:
            return "—"
        try:
            return value.strftime("%d.%m.%Y %H:%M")
        except Exception:
            return str(value)

    async def _add_history(
        self,
        task_id: int,
        user,
        field: str,
        old_value: str = "",
        new_value: str = "",
    ):
        try:
            await TaskHistory.objects.acreate(
                task_id=task_id,
                user_id=getattr(user, "id", None),
                field=field,
                old_value=old_value or "",
                new_value=new_value or "",
            )
        except Exception as exc:
            logging.error(f"Create history error: {exc}")

    @login_required
    async def creation_page_info(
        self,
        request: AsyncRequest,
    ):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        statuses = Status.objects.order_by("id")
        tags = Tag.objects.filter(user_id=user.id).order_by("name", "id")
        categories = Category.objects.filter(user_id=user.id)

        statuses = [
            StatusRetriveDTO.model_validate(item).model_dump()
            async for item in statuses
        ]
        tags = [
            TagRetrieveDTO.model_validate(item).model_dump()
            async for item in tags
        ]
        categories = [
            CategoryRetriveDTO.model_validate(item).model_dump()
            async for item in categories
        ]

        return Response(data={
            'statuses': statuses,
            'tags': tags,
            'categories': categories,
        })

    @login_required
    async def create_tag(
        self,
        request: AsyncRequest,
    ):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            dto = TagCreateDTO(**(request.data or {}))
        except Exception:
            return Response(data={'detail': 'Некорректные данные'}, status=status.HTTP_400_BAD_REQUEST)

        name = (dto.name or "").strip()
        if not name:
            return Response(data={'detail': 'Название не может быть пустым'}, status=status.HTTP_400_BAD_REQUEST)
        if len(name) > 63:
            return Response(data={'detail': 'Название слишком длинное (макс. 63)'}, status=status.HTTP_400_BAD_REQUEST)

        existing = await Tag.objects.filter(name__iexact=name, user_id=user.id).afirst()
        if existing:
            return Response(data=TagRetrieveDTO.model_validate(existing).model_dump(), status=status.HTTP_200_OK)

        tag = await Tag.objects.acreate(name=name, user_id=user.id)
        return Response(data=TagRetrieveDTO.model_validate(tag).model_dump(), status=status.HTTP_201_CREATED)

    async def check_timing(
        self,
        task_create_dto,
        user_id: int,
    ) -> TaskCreateErrorDTO:
        task_create_error_dto = TaskCreateErrorDTO()

        if task_create_dto.started_at is None or task_create_dto.finished_at is None:
            return task_create_error_dto

        if task_create_dto.started_at > task_create_dto.finished_at:
            task_create_error_dto.can_create = False
            task_create_error_dto.detail = 'Время начала не может быть больше времени окончания!'
            return task_create_error_dto

        overlap = await Task.objects.filter(
            user_id=user_id,
            started_at__isnull=False,
            finished_at__isnull=False,
            started_at__lt=task_create_dto.finished_at,
            finished_at__gt=task_create_dto.started_at,
        ).aexists()

        if not overlap:
            return task_create_error_dto

        task_create_error_dto.can_create = False
        task_create_error_dto.detail = 'Нельзя создать задачу на это время'

        prev_task = await Task.objects.filter(
            user_id=user_id,
            started_at__isnull=False,
            finished_at__isnull=False,
            finished_at__lte=task_create_dto.started_at,
        ).order_by('-finished_at').afirst()
        if prev_task:
            task_create_error_dto.available_start = prev_task.finished_at

        next_task = await Task.objects.filter(
            user_id=user_id,
            started_at__isnull=False,
            finished_at__isnull=False,
            started_at__gte=task_create_dto.finished_at,
        ).order_by('started_at').afirst()
        if next_task:
            task_create_error_dto.available_end = next_task.started_at

        return task_create_error_dto

    @staticmethod
    def _normalize_dt_for_history(value) -> str:
        if value is None:
            return "—"
        try:
            return value.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            return str(value)

    @staticmethod
    def _to_naive(dt):
        if dt is None:
            return None
        if timezone.is_aware(dt):
            return timezone.make_naive(dt, timezone.get_current_timezone())
        return dt

    @staticmethod
    def _to_aware(dt):
        if dt is None:
            return None
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    async def _compute_free_slots(self, user_id: int, start_dt, end_dt) -> list[PlannerTimeSlot]:
        start_aware = self._to_aware(start_dt)
        end_aware = self._to_aware(end_dt)
        if start_aware is None or end_aware is None or end_aware <= start_aware:
            return []

        busy = []
        # Exclude recurring tasks logic can be added here later if needed
        # For now, just check overlapping concrete tasks
        qs = Task.objects.filter(
            user_id=user_id,
            started_at__isnull=False,
            finished_at__isnull=False,
            started_at__lt=end_aware,
            finished_at__gt=start_aware,
        ).order_by("started_at")

        async for t in qs:
            s = max(t.started_at, start_aware)
            e = min(t.finished_at, end_aware)
            if s < e:
                busy.append((s, e))

        if not busy:
            return [PlannerTimeSlot(start=self._to_naive(start_aware), end=self._to_naive(end_aware))]

        busy.sort(key=lambda x: x[0])
        merged = []
        cur_s, cur_e = busy[0]
        for s, e in busy[1:]:
            if s <= cur_e:
                if e > cur_e:
                    cur_e = e
            else:
                merged.append((cur_s, cur_e))
                cur_s, cur_e = s, e
        merged.append((cur_s, cur_e))

        free_slots: list[PlannerTimeSlot] = []
        cursor = start_aware
        for s, e in merged:
            if s > cursor:
                free_slots.append(PlannerTimeSlot(start=self._to_naive(cursor), end=self._to_naive(s)))
            if e > cursor:
                cursor = e
        if cursor < end_aware:
            free_slots.append(PlannerTimeSlot(start=self._to_naive(cursor), end=self._to_naive(end_aware)))

        return free_slots

    @login_required
    async def create(self,  request: AsyncRequest):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        try:
            task_create_dto = TaskCreateDTO(**data)
            subtask_bulk_crreate_dto = SubtaskBulkCreateDTO(**data)
            tags = data.get("tags", [])
            if isinstance(tags, (int, str)):
                tags = [tags]
            if tags is None:
                tags = []
            tags = list(dict.fromkeys(tags))

            created_subtask_names = [s.name.strip() for s in subtask_bulk_crreate_dto.subtasks if s.name and s.name.strip()]
            wants_ai_schedule = (
                task_create_dto.started_at is None
                and (task_create_dto.deadline_at is not None or task_create_dto.finished_at is not None)
            )

            task_payload = task_create_dto.model_dump()
            deadline_at = task_payload.get("deadline_at") or task_payload.get("finished_at")
            task_payload["deadline_at"] = deadline_at
            task_payload["started_at"] = self._to_aware(task_payload.get("started_at"))
            task_payload["finished_at"] = self._to_aware(task_payload.get("finished_at"))
            task_payload["deadline_at"] = self._to_aware(task_payload.get("deadline_at"))
            
            # Ensure repeat_days is a list of integers
            if "repeat_days" in task_payload and task_payload["repeat_days"]:
                task_payload["repeat_days"] = [int(d) for d in task_payload["repeat_days"]]
            else:
                 task_payload["repeat_days"] = []

            # Handle repeat_until
            if "repeat_until" in task_payload and task_payload["repeat_until"]:
                try:
                    # It might be a string if coming from raw JSON, or date object if parsed by Pydantic
                    if isinstance(task_payload["repeat_until"], str):
                        task_payload["repeat_until"] = datetime.strptime(task_payload["repeat_until"], "%Y-%m-%d").date()
                except Exception:
                     task_payload["repeat_until"] = None
            else:
                task_payload["repeat_until"] = None

            if task_payload.get("status_id") is None:
                default_status = await Status.objects.order_by("id").afirst()
                if default_status:
                    task_payload["status_id"] = default_status.id

            ai_result = None
            if wants_ai_schedule:
                now = timezone.now()
                deadline_aware = self._to_aware(deadline_at)
                if deadline_aware and deadline_aware > now:
                    free_slots = await self._compute_free_slots(user_id=user.id, start_dt=now, end_dt=deadline_aware)

                    tag_names = []
                    if tags:
                        async for t in Tag.objects.filter(id__in=tags, user_id=user.id):
                            tag_names.append(t.name)

                    wake = getattr(user, "wake_up_time", None)
                    bed = getattr(user, "bed_time", None)
                    wake_up_time = wake.strftime("%H:%M") if wake else "08:00"
                    bed_time = bed.strftime("%H:%M") if bed else "23:00"

                    planner_task = PlannerTaskInput(
                        title=task_create_dto.name,
                        description=task_create_dto.description or "",
                        tags=tag_names,
                        wake_up_time=wake_up_time,
                        bed_time=bed_time,
                        free_slots=free_slots,
                        deadline=self._to_naive(deadline_aware),
                    )

                    try:
                        ai_result = await sync_to_async(analyze_task, thread_sensitive=False)(planner_task)
                    except Exception as exc:
                        logging.exception("AI planning error")
                        ai_result = None

                if ai_result and ai_result.scheduling and ai_result.scheduling.is_scheduled and ai_result.scheduling.slot:
                    task_payload["started_at"] = self._to_aware(ai_result.scheduling.slot.start)
                    task_payload["finished_at"] = self._to_aware(ai_result.scheduling.slot.end)
                else:
                    task_payload["started_at"] = None
                    task_payload["finished_at"] = None

            if not wants_ai_schedule:
                task_create_error_dto = await self.check_timing(task_create_dto=task_create_dto, user_id=user.id)
                if not task_create_error_dto.can_create:
                    detail = task_create_error_dto.detail or "Нельзя создать задачу на это время"
                    if task_create_error_dto.available_start:
                        detail += f"\nДата и время начала доступна с {self._format_dt(task_create_error_dto.available_start)}"
                    if task_create_error_dto.available_end:
                        detail += f"\nДата и время окончания доступна до {self._format_dt(task_create_error_dto.available_end)}"
                    return Response(data={'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

            allowed_tag_ids = []
            if tags:
                async for t in Tag.objects.filter(id__in=tags, user_id=user.id):
                    allowed_tag_ids.append(t.id)
            if len(allowed_tag_ids) != len(tags):
                return Response(data={'detail': 'Некорректные тэги'}, status=status.HTTP_400_BAD_REQUEST)

            task = await Task.objects.acreate(**task_payload, user_id=user.id)
            await task.tags.aset(allowed_tag_ids)

            ai_actions = []
            if wants_ai_schedule and not created_subtask_names and ai_result and ai_result.actions:
                seen = set()
                for a in ai_result.actions:
                    name = str(a).strip()
                    if not name:
                        continue
                    key = name.casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    ai_actions.append(name[:127])

            subtask_objects = []
            for subtask in subtask_bulk_crreate_dto.subtasks:
                if not subtask.name or not subtask.name.strip():
                    continue
                subtask_objects.append(Subtask(**subtask.model_dump(), task_id=task.id))
            for name in ai_actions:
                subtask_objects.append(Subtask(name=name, completed=False, task_id=task.id))

            if subtask_objects:
                await sync_to_async(Subtask.objects.bulk_create)(subtask_objects)

            await self._add_history(
                task_id=task.id,
                user=user,
                field="Задача",
                old_value="",
                new_value="Создана",
            )

            if deadline_at is not None:
                await self._add_history(
                    task_id=task.id,
                    user=user,
                    field="Дедлайн",
                    old_value="—",
                    new_value=self._format_dt(self._to_aware(deadline_at)),
                )

            if wants_ai_schedule:
                if ai_result and ai_result.scheduling and ai_result.scheduling.is_scheduled and ai_result.scheduling.slot:
                    await self._add_history(
                        task_id=task.id,
                        user=user,
                        field="Планирование (AI)",
                        old_value="—",
                        new_value=f"{self._format_dt(task.started_at)} → {self._format_dt(task.finished_at)}",
                    )
                else:
                    await self._add_history(
                        task_id=task.id,
                        user=user,
                        field="Планирование (AI)",
                        old_value="—",
                        new_value=(ai_result.scheduling.message if ai_result and ai_result.scheduling else "Не удалось запланировать"),
                    )

            if ai_actions:
                await self._add_history(
                    task_id=task.id,
                    user=user,
                    field="Подзадачи (AI)",
                    old_value="—",
                    new_value=self._history_text(", ".join(ai_actions)),
                )

            return Response(
                data={'id':  task.id},
                status=status.HTTP_201_CREATED
            )

        except Exception as exc:
            logging.error(exc)
            return Response(status=status.HTTP_400_BAD_REQUEST)

    @login_required
    async def update_subtask_completed(self, request: AsyncRequest, task_id: int, subtask_id: int):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        dto = SubtaskCompletedUpdateDTO(**request.data) if request.data else SubtaskCompletedUpdateDTO()
        try:
            subtask = await Subtask.objects.select_related('task').aget(
                id=subtask_id,
                task_id=task_id,
                task__user_id=user.id,
            )
        except Subtask.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        new_completed = (not subtask.completed) if dto.completed is None else bool(dto.completed)
        if new_completed == subtask.completed:
            return Response(status=status.HTTP_200_OK)

        old_text = "Выполнена" if subtask.completed else "Не выполнена"
        new_text = "Выполнена" if new_completed else "Не выполнена"

        subtask.completed = new_completed
        await subtask.asave(update_fields=["completed"])

        await self._add_history(
            task_id=task_id,
            user=user,
            field=f"Подзадача: {self._history_text(subtask.name)}",
            old_value=old_text,
            new_value=new_text,
        )

        return Response(status=status.HTTP_200_OK)

    @login_required
    async def update(self, request: AsyncRequest, task_id: int):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        try:
            task_update_dto = TaskCreateDTO(**data)
            tags = data.get("tags", [])
            if isinstance(tags, (int, str)):
                tags = [tags]
            if tags is None:
                tags = []
            tags = list(dict.fromkeys(tags))

            subtasks_payload = data.get("subtasks", None)
            if subtasks_payload is None:
                subtasks_payload = []

            task = await Task.objects.select_related(
                'category',
                'sprint',
                'status',
            ).prefetch_related(
                'tags',
                'subtasks',
            ).aget(id=task_id, user_id=user.id)

            old_name = task.name
            old_description = task.description
            old_started_at = task.started_at
            old_finished_at = task.finished_at
            old_deadline_at = task.deadline_at
            old_status_name = task.status.name if task.status else "—"
            old_status_id = task.status.id if task.status else None
            old_sprint_name = task.sprint.name if task.sprint else "—"
            old_sprint_id = task.sprint.id if task.sprint else None
            old_category_name = task.category.name if task.category else "—"
            old_category_id = task.category.id if task.category else None

            old_tag_ids = []
            async for t in task.tags.all():
                old_tag_ids.append(t.id)

            old_subtask_names = []
            async for s in task.subtasks.all():
                old_subtask_names.append(s.name)

            status_id = task_update_dto.status_id
            category_id = task_update_dto.category_id

            if status_id is not None:
                new_status = await Status.objects.aget(id=status_id)
                task.status = new_status
            else:
                task.status = None

            if "sprint_id" in data:
                sprint_id = task_update_dto.sprint_id
                if sprint_id is not None:
                    new_sprint = await Sprint.objects.aget(id=sprint_id)
                    task.sprint = new_sprint
                else:
                    task.sprint = None

            if category_id is not None:
                new_category = await Category.objects.aget(id=category_id, user_id=user.id)
                task.category = new_category
            else:
                task.category = None

            task.name = task_update_dto.name
            task.description = task_update_dto.description
            task.started_at = self._to_aware(task_update_dto.started_at)
            task.finished_at = self._to_aware(task_update_dto.finished_at)
            new_deadline_at = task_update_dto.deadline_at
            if new_deadline_at is None and task.deadline_at is None and task_update_dto.finished_at is not None:
                new_deadline_at = task_update_dto.finished_at
            task.deadline_at = self._to_aware(new_deadline_at)
            
            task.repeat_days = task_update_dto.repeat_days
            task.repeat_until = task_update_dto.repeat_until

            await task.asave()
            allowed_tag_ids = []
            if tags:
                async for t in Tag.objects.filter(id__in=tags, user_id=user.id):
                    allowed_tag_ids.append(t.id)
            if len(allowed_tag_ids) != len(tags):
                return Response(data={'detail': 'Некорректные тэги'}, status=status.HTTP_400_BAD_REQUEST)
            await task.tags.aset(allowed_tag_ids)

            created_subtasks = []
            updated_subtasks = []
            for item in (subtasks_payload or []):
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                if not name:
                    continue
                sid = item.get("id", None)
                if sid:
                    try:
                        s = await Subtask.objects.aget(id=sid, task_id=task_id)
                    except Subtask.DoesNotExist:
                        continue
                    if s.name != name:
                        s.name = name
                        await s.asave(update_fields=["name"])
                        updated_subtasks.append(name)
                else:
                    created_subtasks.append(Subtask(task_id=task_id, name=name, completed=False))
            if created_subtasks:
                await sync_to_async(Subtask.objects.bulk_create)(created_subtasks)

            new_subtask_names = []
            async for s in Subtask.objects.filter(task_id=task_id).order_by("id"):
                new_subtask_names.append(s.name)
            if old_subtask_names != new_subtask_names:
                await self._add_history(
                    task_id=task_id,
                    user=user,
                    field="Подзадачи",
                    old_value=self._history_text(", ".join(old_subtask_names)),
                    new_value=self._history_text(", ".join(new_subtask_names)),
                )

            if old_name != task.name:
                await self._add_history(task_id=task_id, user=user, field="Название",
                                        old_value=self._history_text(old_name), new_value=self._history_text(task.name))

            if old_description != task.description:
                await self._add_history(task_id=task_id, user=user, field="Описание",
                                        old_value=self._history_text(old_description), new_value=self._history_text(task.description))

            if old_started_at != task.started_at:
                await self._add_history(task_id=task_id, user=user, field="Начало выполнения",
                                        old_value=self._format_dt(old_started_at), new_value=self._format_dt(task.started_at))

            if old_finished_at != task.finished_at:
                await self._add_history(task_id=task_id, user=user, field="Конец выполнения",
                                        old_value=self._format_dt(old_finished_at), new_value=self._format_dt(task.finished_at))

            if old_deadline_at != task.deadline_at:
                await self._add_history(task_id=task_id, user=user, field="Дедлайн",
                                        old_value=self._format_dt(old_deadline_at), new_value=self._format_dt(task.deadline_at))

            new_status_id = task.status.id if task.status else None
            if old_status_id != new_status_id:
                new_status_name = task.status.name if task.status else "—"
                await self._add_history(task_id=task_id, user=user, field="Статус",
                                        old_value=self._history_text(old_status_name), new_value=self._history_text(new_status_name))

            new_sprint_id = task.sprint.id if task.sprint else None
            if old_sprint_id != new_sprint_id:
                new_sprint_name = task.sprint.name if task.sprint else "—"
                await self._add_history(task_id=task_id, user=user, field="Спринт",
                                        old_value=self._history_text(old_sprint_name), new_value=self._history_text(new_sprint_name))

            new_category_id = task.category.id if task.category else None
            if old_category_id != new_category_id:
                new_category_name = task.category.name if task.category else "—"
                await self._add_history(task_id=task_id, user=user, field="Сфера",
                                        old_value=self._history_text(old_category_name), new_value=self._history_text(new_category_name))

            new_tag_ids = []
            async for t in task.tags.all():
                new_tag_ids.append(t.id)
            if set(old_tag_ids) != set(new_tag_ids):
                old_tag_names = []
                async for t in Tag.objects.filter(id__in=old_tag_ids):
                    old_tag_names.append(t.name)
                new_tag_names = []
                async for t in Tag.objects.filter(id__in=new_tag_ids):
                    new_tag_names.append(t.name)
                await self._add_history(task_id=task_id, user=user, field="Тэги",
                                        old_value=self._history_text(", ".join(old_tag_names)),
                                        new_value=self._history_text(", ".join(new_tag_names)))

            return Response(data={'id': task.id}, status=status.HTTP_200_OK)
        except Task.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logging.error(f"Update task error: {exc}")
            return Response(data={'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @login_required
    async def update_timing(self, request: AsyncRequest, task_id: int):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            dto = TaskTimingUpdateDTO(**request.data)
            new_started_at = self._to_aware(dto.started_at)
            new_finished_at = self._to_aware(dto.finished_at)

            if new_started_at is None or new_finished_at is None:
                return Response(data={"detail": "Нужно передать started_at и finished_at"}, status=status.HTTP_400_BAD_REQUEST)
            if new_started_at >= new_finished_at:
                return Response(data={"detail": "Время начала не может быть больше времени окончания!"}, status=status.HTTP_400_BAD_REQUEST)

            task = await Task.objects.aget(id=task_id, user_id=user.id)
            old_started_at = task.started_at
            old_finished_at = task.finished_at

            overlap = await Task.objects.filter(
                user_id=user.id,
                started_at__isnull=False,
                finished_at__isnull=False,
                started_at__lt=new_finished_at,
                finished_at__gt=new_started_at,
            ).exclude(id=task_id).aexists()

            if overlap:
                detail = "Нельзя переместить задачу на это время"

                prev_task = await Task.objects.filter(
                    user_id=user.id,
                    started_at__isnull=False,
                    finished_at__isnull=False,
                    finished_at__lte=new_started_at,
                ).exclude(id=task_id).order_by('-finished_at').afirst()
                if prev_task:
                    detail += f"\nДата и время начала доступна с {self._format_dt(prev_task.finished_at)}"

                next_task = await Task.objects.filter(
                    user_id=user.id,
                    started_at__isnull=False,
                    finished_at__isnull=False,
                    started_at__gte=new_finished_at,
                ).exclude(id=task_id).order_by('started_at').afirst()
                if next_task:
                    detail += f"\nДата и время окончания доступна до {self._format_dt(next_task.started_at)}"

                return Response(data={"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

            task.started_at = new_started_at
            task.finished_at = new_finished_at
            await task.asave(update_fields=["started_at", "finished_at"])

            if old_started_at != task.started_at:
                await self._add_history(
                    task_id=task.id,
                    user=user,
                    field="Начало выполнения",
                    old_value=self._format_dt(old_started_at),
                    new_value=self._format_dt(task.started_at),
                )

            if old_finished_at != task.finished_at:
                await self._add_history(
                    task_id=task.id,
                    user=user,
                    field="Конец выполнения",
                    old_value=self._format_dt(old_finished_at),
                    new_value=self._format_dt(task.finished_at),
                )

            return Response(data={
                "id": task.id,
                "started_at": self._format_dt(task.started_at),
                "finished_at": self._format_dt(task.finished_at),
            }, status=status.HTTP_200_OK)
        except Task.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logging.error(f"Update timing error: {exc}")
            return Response(data={"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @login_required
    async def retrive(
        self,
        request: AsyncRequest,
        task_id: int,
    ):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            # Use prefetch_related for M2M and select_related for FK to avoid sync DB access in async context
            # during Pydantic validation
            task = await Task.objects.select_related(
                'category',
                'sprint',
                'status',
                'user'
            ).prefetch_related(
                'tags',
                'subtasks'
            ).aget(id=task_id, user_id=user.id)
        except Task.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        task_retrive_dto = TaskRetrieveDTO.model_validate(task)
            
        # Ensure repeat_days is a list (JSONField can sometimes be None or other types if not initialized properly, though default=list helps)
        if task_retrive_dto.repeat_days is None:
            task_retrive_dto.repeat_days = []

        lifecycle, total_dur = await self._calculate_lifecycle(task)
        task_retrive_dto.lifecycle = lifecycle
        task_retrive_dto.total_duration = total_dur

        return Response(data=task_retrive_dto.model_dump())

    @login_required
    async def update_status(self, request: AsyncRequest, task_id: int):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            status_dto = TaskStatusUpdateDTO(**request.data)
            task = await Task.objects.select_related('status').aget(id=task_id, user_id=user.id)

            # Verify status exists
            new_status = await Status.objects.aget(id=status_dto.status_id)

            old_status_name = task.status.name if task.status else "—"
            old_status_id = task.status.id if task.status else None
            if old_status_id == new_status.id:
                return Response(status=status.HTTP_200_OK)

            task.status = new_status
            await task.asave(update_fields=["status"])

            await self._add_history(
                task_id=task_id,
                user=user,
                field="Статус",
                old_value=old_status_name,
                new_value=new_status.name,
            )

            return Response(status=status.HTTP_200_OK)
        except (Task.DoesNotExist, Status.DoesNotExist):
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logging.error(f"Update status error: {e}, Data: {request.data}")
            return Response(data={'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @login_required
    async def get_canaban_table(
        self,
        request: AsyncRequest,
    ) -> Response:
        category_id = request.query_params.get("category_id")
        category_id_int = None
        if category_id:
            try:
                category_id_int = int(category_id)
            except Exception:
                category_id_int = None

        task_filter = {"user_id": request.user.id}
        if category_id_int is not None:
            task_filter["category_id"] = category_id_int

        statuses = (
            Status.objects
            .prefetch_related(
                Prefetch(
                    'task_set',
                    queryset=Task.objects.prefetch_related(
                        'subtasks',
                        'tags',
                    ).filter(**task_filter),
                )
            )
            .all()
        )

        canabna_list = [
            CanbanColumnRetriveDTO.model_validate(stat).model_dump()
            async for stat in statuses
        ]


        return Response(
            data=canabna_list,
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _week_start_from_iso(value=None):
        tz = timezone.get_current_timezone()
        now = timezone.localtime(timezone.now(), tz)
        base_date = now.date()

        if value:
            try:
                base_date = datetime.strptime(value, "%Y-%m-%d").date()
            except Exception:
                base_date = now.date()

        monday = base_date - timedelta(days=(base_date.weekday() % 7))
        return timezone.make_aware(datetime.combine(monday, time.min), tz)

    @staticmethod
    def _day_bounds_from_iso(value=None):
        tz = timezone.get_current_timezone()
        now = timezone.localtime(timezone.now(), tz)
        base_date = now.date()

        if value:
            try:
                base_date = datetime.strptime(value, "%Y-%m-%d").date()
            except Exception:
                base_date = now.date()

        start = timezone.make_aware(datetime.combine(base_date, time.min), tz)
        end = start + timedelta(days=1)
        return start, end

    @staticmethod
    def _split_into_day_segments(start_dt, end_dt, clamp_start, clamp_end):
        tz = timezone.get_current_timezone()
        start_dt = timezone.localtime(max(start_dt, clamp_start), tz)
        end_dt = timezone.localtime(min(end_dt, clamp_end), tz)
        if start_dt >= end_dt:
            return []

        cursor = start_dt
        segments = []
        while cursor < end_dt:
            next_midnight = timezone.make_aware(
                datetime.combine(cursor.date() + timedelta(days=1), time.min),
                tz,
            )
            seg_end = min(end_dt, next_midnight)
            if seg_end <= cursor:
                break
            segments.append((cursor, seg_end))
            cursor = seg_end
        return segments

    @login_required
    async def list_today(self, request: AsyncRequest):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        day_start, day_end = self._day_bounds_from_iso(request.query_params.get("date"))
        now = timezone.localtime(timezone.now(), timezone.get_current_timezone())
        now_ts = int(now.timestamp())

        timed_qs = (
            Task.objects.filter(
                user_id=user.id,
                started_at__isnull=False,
                started_at__lt=day_end,
            )
            .filter(Q(finished_at__gt=day_start) | Q(finished_at__isnull=True))
            .select_related("status")
            .order_by("started_at")
        )

        timed_tasks = []
        timed_ids = set()

        async for t in timed_qs:
            end_dt = t.finished_at or now
            segments = self._split_into_day_segments(t.started_at, end_dt, day_start, day_end)
            if not segments:
                continue

            s, e = segments[0]
            timed_tasks.append({
                "id": t.id,
                "title": t.name,
                "start_ts": int(s.timestamp()),
                "end_ts": int(e.timestamp()),
                "status_type": getattr(t.status, "type", None),
                "status_name": getattr(t.status, "name", None),
                "status_color": getattr(t.status, "color", None),
            })
            timed_ids.add(t.id)

        deadline_qs = (
            Task.objects.filter(
                user_id=user.id,
                deadline_at__isnull=False,
                deadline_at__gte=day_start,
                deadline_at__lt=day_end,
            )
            .exclude(id__in=timed_ids)
            .select_related("status")
            .order_by("deadline_at")
        )

        deadline_tasks = [
            {
                "id": t.id,
                "title": t.name,
                "deadline_ts": int(timezone.localtime(t.deadline_at).timestamp()),
                "status_type": getattr(t.status, "type", None),
                "status_name": getattr(t.status, "name", None),
                "status_color": getattr(t.status, "color", None),
            }
            async for t in deadline_qs
        ]

        loose_qs = (
            Task.objects.filter(
                user_id=user.id,
                started_at__isnull=True,
                finished_at__isnull=True,
            )
            .exclude(status__type__in=[StatusType.completed.value, StatusType.cancelled.value])
            .select_related("status")
            .order_by("-created_at")
        )

        loose_tasks = [
            {
                "id": t.id,
                "title": t.name,
                "status_type": getattr(t.status, "type", None),
                "status_name": getattr(t.status, "name", None),
                "status_color": getattr(t.status, "color", None),
            }
            async for t in loose_qs
        ]

        total = len(timed_tasks) + len(deadline_tasks) + len(loose_tasks)
        completed = sum(
            1
            for item in (timed_tasks + deadline_tasks + loose_tasks)
            if item.get("status_type") == StatusType.completed.value
        )

        return Response(
            data={
                "date": timezone.localtime(day_start).date().strftime("%Y-%m-%d"),
                "day_start_ts": int(timezone.localtime(day_start).timestamp()),
                "day_end_ts": int(timezone.localtime(day_end).timestamp()),
                "now_ts": now_ts,
                "summary": {
                    "total": total,
                    "completed": completed,
                },
                "timed": timed_tasks,
                "deadlines": deadline_tasks,
                "loose": loose_tasks,
            },
            status=status.HTTP_200_OK,
        )

    @login_required
    async def list_calendar(self, request: AsyncRequest):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        week_start = self._week_start_from_iso(request.query_params.get("week_start"))
        week_end = week_start + timedelta(days=7)

        qs = (
            Task.objects.filter(
                user_id=user.id,
                started_at__isnull=False,
                finished_at__isnull=False,
                started_at__lt=week_end,
                finished_at__gt=week_start,
            )
            .order_by("started_at")
        )

        tasks = []
        async for t in qs:
            segments = self._split_into_day_segments(t.started_at, t.finished_at, week_start, week_end)
            if not segments:
                continue
            if len(segments) == 1:
                s, e = segments[0]
                tasks.append({
                    "id": t.id,
                    "title": t.name,
                    "started_at": self._format_dt(s),
                    "ended_at": self._format_dt(e),
                })
                continue

            for idx, (s, e) in enumerate(segments, start=1):
                tasks.append({
                    "id": f"{t.id}:{idx}",
                    "source_id": t.id,
                    "title": t.name,
                    "started_at": self._format_dt(s),
                    "ended_at": self._format_dt(e),
                })

        week_days = []
        week_day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        cur = timezone.localtime(week_start).date()
        for i in range(7):
            d = cur + timedelta(days=i)
            week_days.append({
                "iso": d.strftime("%Y-%m-%d"),
                "date_key": d.strftime("%d.%m.%Y"),
                "label": f"{week_day_names[i]}, {d.day}",
            })

        return Response(data={
            "week_start": timezone.localtime(week_start).date().strftime("%Y-%m-%d"),
            "week_end": timezone.localtime(week_end - timedelta(seconds=1)).date().strftime("%Y-%m-%d"),
            "days": week_days,
            "tasks": tasks,
        }, status=status.HTTP_200_OK)

    @login_required
    async def create_comment(self, request: AsyncRequest, task_id: int):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            comment_dto = CommentCreateDTO(**request.data)
            task = await Task.objects.aget(id=task_id, user_id=user.id)
            
            comment = await Comment.objects.acreate(
                user=user,
                task=task,
                text=comment_dto.text
            )

            await self._add_history(
                task_id=task_id,
                user=user,
                field="Комментарий",
                old_value="",
                new_value="Добавлен",
            )

            response_dto = CommentRetrieveDTO(
                id=comment.id,
                text=comment.text,
                created_at=comment.created_at,
                user_id=user.id,
                user_name=user.username  # Assuming User model has username field
            )

            return Response(data=response_dto.model_dump(), status=status.HTTP_201_CREATED)
        except Task.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logging.error(f"Create comment error: {e}")
            return Response(data={'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @login_required
    async def list_comments(self, request: AsyncRequest, task_id: int):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            # Check if task exists and belongs to user
            await Task.objects.aget(id=task_id, user_id=user.id)
            
            comments = Comment.objects.filter(task_id=task_id).select_related('user').order_by('-created_at')
            
            comment_list = [
                CommentRetrieveDTO(
                    id=comment.id,
                    text=comment.text,
                    created_at=comment.created_at,
                    user_id=comment.user.id,
                    user_name=comment.user.username
                ).model_dump()
                async for comment in comments
            ]

            return Response(data=comment_list, status=status.HTTP_200_OK)
        except Task.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logging.error(f"List comments error: {e}")
            return Response(data={'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @login_required
    async def list_history(self, request: AsyncRequest, task_id: int):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            await Task.objects.aget(id=task_id, user_id=user.id)
            items = TaskHistory.objects.filter(task_id=task_id).select_related('user').order_by('-created_at')
            history_list = [
                TaskHistoryRetrieveDTO(
                    id=item.id,
                    field=item.field,
                    old_value=item.old_value,
                    new_value=item.new_value,
                    created_at=item.created_at,
                    user_id=item.user.id if item.user else None,
                    user_name=item.user.username if item.user else None,
                ).model_dump()
                async for item in items
            ]
            return Response(data=history_list, status=status.HTTP_200_OK)
        except Task.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logging.error(f"List history error: {e}")
            return Response(data={'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
