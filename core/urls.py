"""Public website URL patterns."""

from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path('discover/', views.home_page, name='web-home'),
    path('create-account/', views.register_page, name='web-register'),
    path('sign-in/', views.login_page, name='web-login'),
    path('sign-out/', views.logout_page, name='web-logout'),
    path('my-profile/', views.profile_page, name='web-profile'),
    path('recipe-studio/', views.create_recipe_page, name='web-recipe-create'),
    path('recipe/<int:recipe_id>/', views.recipe_detail_page, name='web-recipe-detail'),
    path('recipe/<int:recipe_id>/review/', views.add_review_page, name='web-recipe-review'),
    path('recipe/<int:recipe_id>/report/', views.report_recipe_page, name='web-report-recipe'),
    path('recipe/<int:recipe_id>/status/', views.update_recipe_status_page, name='web-recipe-status'),
    path('recipe/<int:recipe_id>/delete/', views.delete_recipe_page, name='web-recipe-delete'),
    path('review/<int:review_id>/react/', views.add_reaction_page, name='web-review-react'),
    path('review/<int:review_id>/report/', views.report_review_page, name='web-report-review'),
    path('review/<int:review_id>/delete/', views.delete_review_page, name='web-review-delete'),
    path('report-queue/', views.report_queue_page, name='web-report-queue'),
    path('report-queue/<int:report_id>/resolve/', views.resolve_report_page, name='web-report-resolve'),
    path('ai-recipe-studio/', views.ai_generate_page, name='web-ai-generate'),
    path('boards/', views.boards_page, name='web-boards'),
    path('', RedirectView.as_view(pattern_name='web-home', permanent=False), name='web-home-root'),
]
