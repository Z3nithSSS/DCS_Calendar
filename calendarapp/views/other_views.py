# cal/views.py

from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.views import generic
from django.utils.safestring import mark_safe
from datetime import timedelta, datetime, date
import calendar
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib import messages
import logging

from calendarapp.models import EventMember, Event, Team
from calendarapp.utils import Calendar
from calendarapp.forms import EventForm, AddMemberForm
from django.db.models import Prefetch
from django.db import IntegrityError

logger = logging.getLogger(__name__)


def is_moderator(user):
    return user.groups.filter(name='moderator').exists()


def get_date(req_day):
    if req_day:
        year, month = (int(x) for x in req_day.split("-"))
        return date(year, month, day=1)
    return datetime.today()


def prev_month(d):
    first = d.replace(day=1)
    prev_month = first - timedelta(days=1)
    month = "month=" + str(prev_month.year) + "-" + str(prev_month.month)
    return month


def next_month(d):
    days_in_month = calendar.monthrange(d.year, d.month)[1]
    last = d.replace(day=days_in_month)
    next_month = last + timedelta(days=1)
    month = "month=" + str(next_month.year) + "-" + str(next_month.month)
    return month


class CalendarView(LoginRequiredMixin, generic.ListView):
    login_url = "accounts:signin"
    model = Event
    template_name = "calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        d = get_date(self.request.GET.get("month", None))
        cal = Calendar(d.year, d.month)
        html_cal = cal.formatmonth(withyear=True)
        context["calendar"] = mark_safe(html_cal)
        context["prev_month"] = prev_month(d)
        context["next_month"] = next_month(d)
        return context


@login_required(login_url="signup")
@user_passes_test(is_moderator)
def create_event(request):
    form = EventForm(request.POST or None)
    if request.POST and form.is_valid():
        title = form.cleaned_data["title"]
        description = form.cleaned_data["description"]
        start_time = form.cleaned_data["start_time"]
        end_time = form.cleaned_data["end_time"]
        Event.objects.get_or_create(
            user=request.user,
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
        )
        return HttpResponseRedirect(reverse("calendarapp:calendar"))
    return render(request, "event.html", {"form": form})


class EventEdit(generic.UpdateView):
    model = Event
    fields = ["title", "description", "start_time", "end_time"]
    template_name = "event.html"


@login_required(login_url="signup")
def event_details(request, event_id):
    event = Event.objects.get(id=event_id)
    eventmember = EventMember.objects.filter(event=event)
    context = {"event": event, "eventmember": eventmember}
    return render(request, "event-details.html", context)


def add_eventmember(request, event_id):
    forms = AddMemberForm()
    if request.method == "POST":
        forms = AddMemberForm(request.POST)
        if forms.is_valid():
            member = EventMember.objects.filter(event=event_id)
            event = Event.objects.get(id=event_id)
            if member.count() <= 9:
                user = forms.cleaned_data["user"]
                EventMember.objects.create(event=event, user=user)
                return redirect("calendarapp:calendar")
            else:
                print("--------------User limit exceed-----------------")
    context = {"form": forms}
    return render(request, "add_member.html", context)


class EventMemberDeleteView(generic.DeleteView):
    model = EventMember
    template_name = "event_delete.html"
    success_url = reverse_lazy("calendarapp:calendar")

class CalendarViewNew(LoginRequiredMixin, generic.View):
    login_url = "accounts:signin"
    template_name = "calendarapp/calendar.html"
    form_class = EventForm

    def get(self, request, *args, **kwargs):
        forms = self.form_class()
        events = Event.objects.get_all_events(user=request.user)
        events_month = Event.objects.get_running_events(user=request.user)
        event_list = []
        # start: '2020-09-16T16:00:00'
        for event in events:
            event_list.append(
                {   "id": event.id,
                    "title": event.title,
                    "start": event.start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "end": event.end_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "description": event.description,
                }
            )
        
        context = {"form": forms, "events": event_list,
                   "events_month": events_month}
        return render(request, self.template_name, context)

    @user_passes_test(is_moderator)
    def post(self, request, *args, **kwargs):
        forms = self.form_class(request.POST)
        if forms.is_valid():
            form = forms.save(commit=False)
            form.user = request.user
            form.save()
            return redirect("calendarapp:calendar")
        else: 
            messages.error('The user is not  amo')
        context = {"form": forms}
        return render(request, self.template_name, context)


@user_passes_test(is_moderator)
def delete_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        event.delete()
        return JsonResponse({'message': 'Event sucess delete.'})
    else:
        return JsonResponse({'message': 'Error!'}, status=400)

@user_passes_test(is_moderator)
def next_week(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        next = event
        next.id = None
        next.start_time += timedelta(days=7)
        next.end_time += timedelta(days=7)
        next.save()
        return JsonResponse({'message': 'Sucess!'})
    else:
        return JsonResponse({'message': 'Error!'}, status=400)

@user_passes_test(is_moderator)
def next_day(request, event_id):

    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        next = event
        next.id = None
        next.start_time += timedelta(days=1)
        next.end_time += timedelta(days=1)
        next.save()
        return JsonResponse({'message': 'Sucess!'})
    else:
        return JsonResponse({'message': 'Error!'}, status=400)
    

def attend_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    teams = Team.objects.filter(event=event)
    team_created = False
    team_id = None

    # Handle Team Creation
    if request.method == "POST" and 'team_name' in request.POST:
        team_name = request.POST.get('team_name')

        # Check if team name is not empty
        if not team_name:
            messages.error(request, 'You must enter the name of the team!')
        # Check if team name is unique within the event
        elif Team.objects.filter(event=event, name=team_name).exists():
            messages.error(request, 'A team with this name already exists for this event!')
        else:
            Team.objects.create(event=event, name=team_name)
            team_created = True
            teams = Team.objects.filter(event=event)
            messages.success(request, 'Team created successfully!')        
            

    # Event Attendance Handling 
    if request.method == "POST" and 'email' in request.POST:  
        email = request.POST.get('email')
        nickname = request.POST.get('nickname')
        role = request.POST.get('role')
        team_id = request.POST.get('team_id')

    try:
        selected_team = Team.objects.get(id=team_id, event=event)
        
        # Check if an EventMember already exists with this event, team, and role
        existing_member = EventMember.objects.filter(
            user=request.user,
            event=event, 
            team=selected_team, 
            role=role
        )

        email_event_scope = EventMember.objects.filter(
            event=event,
            email=email
        )
        
        if existing_member.exists():
            messages.error(request, "An event member with this data already exists!")
        elif email_event_scope.exists():
            messages.error(request, "The user with this email exists in this event")    
        else:
            EventMember.objects.create(
                event=event, 
                user=request.user,
                email=email, 
                nickname=nickname,
                role=role,
                team=selected_team 
            )
            messages.success(request, "Event member added successfully.")
            
    except Team.DoesNotExist:
        messages.error(request, 'Selected team does not exist!')
    except IntegrityError as e:
        messages.error(request, "An event member with this role in the selected team already exists.") 
       

    context = {
        'event_id': event_id,
        'event_title': event.title,
        'teams': teams,
        'team_created': team_created
    }
    return render(request, 'role.html', context)



def event_info(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    team_members_qs = EventMember.objects.only("nickname", "role", "email")
    teams = event.teams.prefetch_related(Prefetch("members", queryset=team_members_qs))
    context = {
        'event': event,
        'teams': teams,
    }
    return render(request, 'info.html', context)



# def event_info(request, event_id):
#     event = get_object_or_404(Event, id=event_id)
#     teams_data = []

#     # Get all teams for this event
#     teams = event.teams.all()  # This uses the related_name 'teams' set in Team model

#     for team in teams:
#         # Get all members for this team
#         members_data = [{
#             'nickname': members.nickname,
#             'role': members.role,
#             'email': members.email
#         } for members in team.members.all()]  # Accessing EventMember instances

#         teams_data.append({
#             'name': team.name,
#             'members': members_data
#         })

#     # Add teams_data to the context
#     context = {
#         'event': event,
#         'teams_data': teams_data,
#     }
#     #### ADD logging here via logger or print
#     logger.debug(context)
#     print(context)
#     ####
#     return render(request, 'info.html', context)
             

        
        


