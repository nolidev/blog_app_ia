from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json
from pytube import YouTube
import os
import assemblyai as aai
from openai import OpenAI
from .models import BlogPost
from dotenv import load_dotenv

load_dotenv()


# Create your views here.

# Only a user that is login can access to the index
@login_required
def index(request):
    return render(request, 'index.html')

# Trasncript of the youtube video
@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            # Request the value of the json {dic} in the var body, inside the JS script
            data = json.loads(request.body)
            # Get Youtube link
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)


        # get yt title
        title = yt_title(yt_link)

        # get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error': "Failed to transcript"}, status=500)
        # use OpenIA to generate the blog
        blog_content = generate_blog_transcript(transcription)
        if not blog_content:
            return JsonResponse({'error': "Failed to generate content"}, status=500)
        # save blog article to database
        new_blog_article = BlogPost.objects.create(
            user = request.user,
            youtube_title = title,
            youtube_link = yt_link,
            generated_content = blog_content,
        )
        new_blog_article.save()

        # return blog article as a response
        return JsonResponse({'content': blog_content})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

# Get the title of a youtube video
def yt_title(link):
    yt = YouTube(link)
    title = yt.title
    return title

def download_audio(link):
    yt = YouTube(link)
    video = yt.streams.filter(only_audio=True).first()

    # Download and store the audio in MEDIA ROOT, specifying the path 
    out_file = video.download(output_path=settings.MEDIA_ROOT)

    # Splitext give us two items, then using .mp3 to save the new name of the file 
    base, ext = os.path.splitext(out_file)
    new_file = base + '.mp3'
    os.rename(out_file, new_file)
    return new_file

def get_transcription(link):
    audio_file = download_audio(link)
    API_KEY_AAI = os.getenv('API_KEY_AAI')
    aai.settings.api_key = API_KEY_AAI
    

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)

    return transcript.text

def generate_blog_transcript(transcription):
    API_KEY_OPENAI = os.getenv('API_KEY_OPENAI')
    client = OpenAI(api_key=API_KEY_OPENAI)

    # Tell OpenAI what to do
    prompt = f"Basándote en la siguiente transcripción de un video de youtube, escribe un articulo completo para un blog. El articulo estará basado en la transcripción, pero no lo hagas parecer a un video de youtube haz que se parezca a un articulo de un blog en español:\n\n{transcription}\n\nArticle:"

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role":"user",
                "content":prompt
            }
        ],
        model="gpt-3.5-turbo"
    )
    generated_content = chat_completion.choices[0].message.content

    return generated_content

def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, 'blogs.html', {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)

    # Check if user currently logged in is the owner of that article
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

    # Authenticate the user in the page, using authenticate 
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = 'Invalid username or password'
            return render(request, 'login.html', {'error_message': error_message})
    return render(request, 'login.html')

def user_signup(request):
    # Receive data from signup form
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        confirmPassword = request.POST['confirmPassword']

        # Checks if passwords are the same. Then the user login and is redirected to the index page
        if password == confirmPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message': error_message})
        # If the passwd are not the same
        else:
            error_message = 'Password do not match.'
            return render(request, 'signup.html', {'error_message': error_message})
    return render(request, 'signup.html')

# User logout
def user_logout(request):
    logout(request)
    return redirect('/')

