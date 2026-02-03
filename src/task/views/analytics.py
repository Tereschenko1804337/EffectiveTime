from adrf.requests import AsyncRequest
from adrf.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from asgiref.sync import sync_to_async
from django.shortcuts import render

from task.models import Task, Status, TaskHistory
from infrastructure.comon.authetication import AsyncAuthentication
from infrastructure.comon.login_decorator import login_required
from infrastructure.ai.openrouter_analyst import analyze_productivity, AnalysisInput

class AnalyticsAsyncViewSet(ViewSet):
    authentication_classes = [AsyncAuthentication]

    @login_required
    async def get_page(self, request: AsyncRequest):
        return render(request, "analytics.html")

    @staticmethod
    def _calculate_batch_lifecycle(tasks, histories, status_map):
        """
        Aggregates time spent in each status across multiple tasks.
        Returns: { "Status Name": total_seconds }
        """
        # Group histories by task_id
        hist_by_task = {}
        for h in histories:
            if h.task_id not in hist_by_task:
                hist_by_task[h.task_id] = []
            hist_by_task[h.task_id].append(h)

        status_durations = {} # { "StatusName": seconds }
        
        now = timezone.now()

        for task in tasks:
            task_history = hist_by_task.get(task.id, [])
            # Sort history by created_at just in case
            task_history.sort(key=lambda x: x.created_at)

            current_status = "Новый" # Default
            if task_history:
                current_status = task_history[0].old_value
            elif task.status:
                current_status = task.status.name
            
            cursor = task.created_at
            
            for item in task_history:
                end = item.created_at
                duration = (end - cursor).total_seconds()
                
                status_durations[current_status] = status_durations.get(current_status, 0) + duration
                
                cursor = end
                current_status = item.new_value
            
            # Final segment
            # Only count until NOW or until finished? 
            # If task is completed, we should ideally stop counting at finish time.
            # But Task model doesn't strictly enforce finished_at matching status change.
            # Let's use task.finished_at if set and status is terminal.
            
            end_time = now
            if task.status and task.status.type in ['completed', 'cancelled'] and task.finished_at:
                end_time = task.finished_at
                # If finished_at is before cursor (weird data), use cursor
                if end_time < cursor:
                    end_time = cursor

            duration = (end_time - cursor).total_seconds()
            status_durations[current_status] = status_durations.get(current_status, 0) + duration

        return status_durations

    @login_required
    async def get_stats(self, request: AsyncRequest):
        user = request.user
        
        @sync_to_async
        def get_data():
            # 1. By Category
            cat_stats = list(Task.objects.filter(user=user)
                             .values('category__name')
                             .annotate(count=Count('id'))
                             .order_by('-count'))
            for item in cat_stats:
                if item['category__name'] is None:
                    item['category__name'] = 'Без категории'

            # 2. By Status
            status_stats = list(Task.objects.filter(user=user)
                                .values('status__name', 'status__color')
                                .annotate(count=Count('id'))
                                .order_by('-count'))
            
            # 3. Created Last 7 Days
            last_week = timezone.now() - timedelta(days=7)
            daily_stats = list(Task.objects.filter(user=user, created_at__gte=last_week)
                               .annotate(date=TruncDate('created_at'))
                               .values('date')
                               .annotate(count=Count('id'))
                               .order_by('date'))
            
            # 4. KPI
            total = Task.objects.filter(user=user).count()
            completed = Task.objects.filter(user=user, status__type='completed').count()
            completion_rate = round((completed / total * 100) if total > 0 else 0, 1)

            # 5. Lifecycle Stats (Active in last 7 days)
            # Find tasks created or modified in last 7 days
            # Actually, let's just take all tasks to give a full picture, or limit to 50 recent?
            # Let's take all non-archived tasks or just all.
            # For "Last Week Analysis", strict filtering is better.
            
            active_tasks = Task.objects.filter(user=user, created_at__gte=last_week).select_related('status')
            # Also include tasks that were finished in last week? 
            # Simplification: Analyze ALL tasks created in last 30 days for better stats
            analyze_tasks = list(Task.objects.filter(user=user, created_at__gte=timezone.now() - timedelta(days=30)))
            
            histories = list(TaskHistory.objects.filter(task__in=analyze_tasks, field="Статус"))
            statuses = list(Status.objects.all())
            status_map = {s.name: s.color for s in statuses}
            
            lifecycle_durations = AnalyticsAsyncViewSet._calculate_batch_lifecycle(analyze_tasks, histories, status_map)
            
            # Format lifecycle for frontend chart { "Status": hours }
            lifecycle_chart = []
            total_lifecycle_seconds = sum(lifecycle_durations.values())
            
            for s_name, seconds in lifecycle_durations.items():
                hours = round(seconds / 3600, 1)
                lifecycle_chart.append({
                    "status": s_name,
                    "seconds": seconds,
                    "hours": hours,
                    "color": status_map.get(s_name, "#ccc")
                })
            
            lifecycle_chart.sort(key=lambda x: x['seconds'], reverse=True)

            return {
                "categories": cat_stats,
                "statuses": status_stats,
                "daily": daily_stats,
                "kpi": {
                    "total": total,
                    "completed": completed,
                    "completion_rate": completion_rate
                },
                "lifecycle": lifecycle_chart
            }

        data = await get_data()
        return Response(data, status=status.HTTP_200_OK)

    @login_required
    async def get_ai_report(self, request: AsyncRequest):
        user = request.user
        
        # Gather data for AI
        # We need stats for the last 7 days specifically
        @sync_to_async
        def gather_ai_data():
            last_week = timezone.now() - timedelta(days=7)
            
            # Tasks created or active? Let's look at completed tasks for "Cycle Time" 
            # and active tasks for "Bottlenecks".
            
            # 1. Total/Completed in last 7 days
            total_new = Task.objects.filter(user=user, created_at__gte=last_week).count()
            completed_new = Task.objects.filter(user=user, status__type='completed', finished_at__gte=last_week).count()
            
            # 2. Cycle Time (avg duration of completed tasks)
            completed_tasks = Task.objects.filter(user=user, status__type='completed', finished_at__gte=last_week)
            durations = []
            for t in completed_tasks:
                if t.finished_at and t.created_at:
                    durations.append((t.finished_at - t.created_at).total_seconds())
            
            avg_cycle = (sum(durations) / len(durations) / 3600) if durations else 0.0
            
            # 3. Status Distribution (Time spent in statuses in the last 7 days)
            # This is complex. Simplified: take Lifecycle stats of tasks active in last 7 days.
            # Reusing logic from get_stats but slightly adapted
            active_tasks = list(Task.objects.filter(user=user, created_at__gte=last_week))
            histories = list(TaskHistory.objects.filter(task__in=active_tasks, field="Статус"))
            status_map = {} # Not needed for AI input
            
            durations_map = AnalyticsAsyncViewSet._calculate_batch_lifecycle(active_tasks, histories, status_map)
            
            # Format durations for AI
            status_dist_str = {}
            for k, v in durations_map.items():
                hours = round(v / 3600, 1)
                status_dist_str[k] = f"{hours} ч."

            # 4. Categories
            cats = Task.objects.filter(user=user, created_at__gte=last_week).values('category__name').annotate(c=Count('id'))
            cat_dist = { (c['category__name'] or 'Без категории'): c['c'] for c in cats }
            
            return AnalysisInput(
                total_tasks=total_new,
                completed_tasks=completed_new,
                avg_completion_time_hours=avg_cycle,
                status_distribution=status_dist_str,
                category_distribution=cat_dist
            )

        ai_input = await gather_ai_data()
        
        # Call AI
        # This is async, but analyze_productivity uses sync call_openrouter internally?
        # No, call_openrouter uses urllib which is blocking. 
        # We should wrap it in sync_to_async or run in thread.
        
        @sync_to_async
        def run_ai():
            return analyze_productivity(ai_input)
            
        result = await run_ai()
        
        return Response(result.model_dump(), status=status.HTTP_200_OK)
