# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render, HttpResponse, redirect

from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from PocketStock.forms import RegistrationForm, TransactionAddForm

from django.db.models import Q
import json
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AdminPasswordChangeForm, PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages

from social_django.models import UserSocialAuth

from PocketStock import duo_auth
from datetime import datetime

from stocks.models import TransactionModel, StockStatusModel, StockProfileModel
import requests

# Create your views here.
def home(request):
    if request.user.is_authenticated():
        return registered_home(request)
    else:
        return render(request,'base_generic.html')


@login_required
@duo_auth.duo_auth_required
def registered_home(request):

    #get all transactions made by the current user
    all_entries = TransactionModel.objects.filter(user=request.user)

    #we need to pass the user a series of associated objects with the following characteristics
    #quantity, percent, currentPrice, companyName, valuation

    output_list = []

    companies = []

    #iterate through to get all companies the user has stocks in
    for i in all_entries:
        if i.whichStock not in companies:
            companies.append(i.whichStock)

    company_statuses = {}

    #get the most recent status of the companies that the user has stock in
    for i in companies:
        company_statuses[i] = StockStatusModel.objects.filter(whichStock=i).order_by('date')[0].currentPrice

    # company_fullnames = {}

    # #get the full name of the companies that the user has stock in
    # for i in companies:
    #     company_fullnames[i] = StockProfileModel.objects.get(tickerName=i).fullName

    #Associate all related info
    for i in all_entries:
        obj = {}
        obj['qty'] = i.numberPurchased
        obj['percent'] = round((company_statuses[i.whichStock] - (i.amountSpent / i.numberPurchased)) / (i.amountSpent / i.numberPurchased) * 100, 2)
        obj['currentPrice'] = company_statuses[i.whichStock]
        obj['name'] = i.whichStock
        obj['valuation'] = i.numberPurchased * company_statuses[i.whichStock]
        output_list.append(obj)

    return render(request, 'dashboard.html', {
        'transactions': output_list,
        })


@login_required
@duo_auth.duo_auth_required
def settings(request):
    user = request.user

    try:
        facebook_login = user.social_auth.get(provider='facebook')
    except UserSocialAuth.DoesNotExist:
        facebook_login = None

    can_disconnect = (user.social_auth.count() > 1 or user.has_usable_password())

    return render(request, 'settings.html', {
        'facebook_login': facebook_login,
        'can_disconnect': can_disconnect
        })


@login_required
@duo_auth.duo_auth_required
def password(request):
    if request.user.has_usable_password():
        PasswordForm = PasswordChangeForm
    else:
        PasswordForm = AdminPasswordChangeForm

    if request.method == 'POST':
        form = PasswordForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('password')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordForm(request.user)
    return render(request, 'password.html', {'form': form})


def signup(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('/dashboard')
    else:
        form = RegistrationForm()

    return render(request, 'signup.html', {'form': form})


@login_required
@duo_auth.duo_auth_required
def create_transaction(request):
    if request.method == 'POST':
        form = TransactionAddForm(request.POST)
        if form.is_valid():
            #process data
            form.save(request.user)
            return redirect('/dashboard')
    else:
        form = TransactionAddForm()

    return render(request, 'create_transaction.html', {'form': form})

@login_required
@duo_auth.duo_auth_required
def searchResults(request):
    if request.method == 'GET':
        print 'hi'
        query = request.GET.get('query')
        results = StockProfileModel.objects.filter(Q(tickerName__icontains=query)|Q(fullName__icontains=query))
        print results
        resultsToSend = {}
        for i in range(0, len(results)):
            link = '/stockProfile?stockname='+ results[i].tickerName
            resultsToSend[results[i].fullName] = link
        return render(request, 'searchresults.html', {'searchres': resultsToSend})

def insertData(request):
    k={
        'WFC':'Wells Fargo & Co',
        'WMT' : 'Walmart',
        'GOOGL' : 'Alphabet Inc',
        'XOM' : 'Exxon Mobil Corporation',
        'FB' : 'Facebook',
        'TWTR': 'Twitter',
        'CRM': 'Salesforce.com',
        'ORCL': 'Oracle Corporation',
        'GS': 'Goldman Sachs Group Inc',
        'JPM': 'JPMorgan Chase & Co.',
    }
    #code to companies to the stockprofile model
    '''
    for i in k.keys():
        s = StockProfileModel(tickerName=i, fullName=k[i])
        s.save()
    '''
    #code to add stocks
    tickName = 'JPM'
    respons = requests.get('https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol='+tickName+'&apikey=2NWT4MKPZ594L2GF')
    ll = json.loads(respons.text)
    ll = ll['Time Series (Daily)']
    for i in ll.keys():
        s = i
        s = s + ' 00:00:00'

        datetime_object = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
        s_ins = StockProfileModel.objects.get(tickerName=tickName)
        s = StockStatusModel(whichStock=s_ins, date=datetime_object, highPrice=ll[i]['2. high'], lowPrice = ll[i]['3. low'], currentPrice=ll[i]['4. close'])
        s.save()

@login_required
@duo_auth.duo_auth_required
def getCompanies(request):
    query = request.GET.get('query')
    results = StockProfileModel.objects.all()
    ll = {}
    for result in results:
        ll[result.fullName] = result.fullName
    return HttpResponse(json.dumps(ll) ,content_type="application/json")

@login_required
@duo_auth.duo_auth_required
def stockProfile(request):
    tickerName = request.GET.get('stockname')
    s_ins = StockProfileModel.objects.get(tickerName=tickerName)
    return render(request, 'StockProfile.html',{'stockName': s_ins.fullName,'tickerName':s_ins.tickerName,})