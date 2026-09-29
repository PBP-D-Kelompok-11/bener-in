from django.shortcuts import render


def landing_page(request):
    context = {}

    return render(request, "index.html", context)

def login_user(request):
    pass

def logout_user(request):
    pass

def register(request):
    pass

def show_history(request):
    pass

def show_repair_page(request):
    pass