#!/usr/bin/python
# -*- coding: utf-8 -*- 
# @File Name: views.py
# @Created:   2018-04-17 00:09:27  Simon Myunggun Seo (simon.seo@nyu.edu) 
# @Updated:   2018-04-21 02:38:18  Simon Seo (simon.seo@nyu.edu)
from flask import request, render_template, redirect, url_for, flash

# Built-in
import os
import logging
from hashlib import sha256

# Private Libs
import psycopg2
from passlib.apps import custom_app_context as pwd_context

# My own
from app import app
from app.form import RegistrationForm, PasscodeRequestForm
from app import db
from app import duo
from .exceptions import AuthenticationException, WrongPasswordException, UserDataNotFoundException, UniqueViolationException


def encode_password(password):
    return sha256(password.encode('utf-8')).hexdigest()[:32]

routes = ['generate_passcode', 'register_account']


@app.route("/")
def main():
    return render_template('index.html', title='F**k MFA', urls={r: url_for(r) for r in routes})

@app.route("/tos")
def terms_of_service():
    return render_template('tos.html', title='Terms of Service')

@app.route('/register', methods=['GET', 'POST'])
def register_account():
    form = RegistrationForm(request.form)
    if request.method == 'POST' and form.validate():
        #also check that account does not exist already
        password = pwd_context.hash(form.password.data)
        try:
            hotp_secret = duo.activate(form.qr_url.data)
            # hotp_secret = 'a85adc3516351791c05ef40bde772c24'
            db.insert_user(form.email.data, password, hotp_secret)
        except UniqueViolationException as e:
            flash("An account with that email already exists. Try another one.")
            return redirect(url_for('register_account'))
        except Exception as e:
            flash("I\'m sorry. Try again later. Let the adminstrator know about the error: {} {}".format(type(e), e))
            return redirect(url_for('register_account'))
        else:
            flash("Thanks for registering.")
            app.logger.debug("Received {} {}:{}".format(form.email.data, form.password.data, password))
            return redirect(url_for('generate_passcode'))
    else:
        return render_template('register.html', title='Register New Account', form=form, urls={r: url_for(r) for r in routes})

@app.route('/passcode', methods=['GET', 'POST'])
def generate_passcode():
    form = PasscodeRequestForm(request.form)
    if request.method == 'POST' and form.validate():
        # checking account info should ideally happen in form.validate
        try:
            n=int(form.count.data)
            user = db.get_user(form.email.data)
            if user is not None:
                uid, email, password, hotp_secret, counter = user
            else:
                raise UserDataNotFoundException("No user data was found with the provided email.")
            if not pwd_context.verify(form.password.data, password):
                raise WrongPasswordException("Password does not match the one in the DB.")
        except AuthenticationException as e:
            flash("We\'re sorry. There is no user with the given credentials. Check your email and password.")
            return redirect(url_for('generate_passcode'))
        except Exception as e:
            app.logger.debug("Exception in generate_passcode: {}".format(e))
            flash("I\'m sorry. Try again later. Let the adminstrator know about the error: {}".format(e))
            return redirect(url_for('generate_passcode'))
        
        app.logger.debug("Password verified, hotp_secret:{}".format(hotp_secret))

        try:
            hotp_list = duo.generate_hotp(hotp_secret, current_at=counter, n=n)
            db.update_user(uid, counter=counter+n)
        except Exception as e:
            app.logger.error("Exception while producing new hotp", type(e), e)
            flash("I\'m sorry. Try again later. Let the adminstrator know about the error: {} {}".format(type(e), e))
            return redirect(url_for('generate_passcode'))

        app.logger.debug('We\'ll send an email to {0} with your new passcodes! Received {0} {1} {2} {3} {4}'.format(form.email.data, form.password.data, form.count.data, hotp_secret, hotp_list))
        app.logger.debug("New counter: {}".format(counter+n))
        return render_template('display-passcode.html', title='Retrieved Passcodes', hotp_list=hotp_list, urls={r: url_for(r) for r in routes})
    else:
        return render_template('generate-passcode.html', title='Generate Passcode', form=form, urls={r: url_for(r) for r in routes})


'''
@app.route('/delete', methods=['GET', 'POST'])
def delete_account():
    form = DeleteAccountForm(request.form)
    if request.method == 'POST' and form.validate():
        return redirect(url_for("register_account"))
    return render_template('delete.html', title='Delete Account Information', form=form)

@app.route('/edit', methods=['GET', 'POST'])
def edit_account():
    form = EditAccountForm(request.form)
    if request.method == 'POST' and form.validate():
        return redirect(url_for("generate_passcode"))
    return render_template('edit.html', title='Update Account Information', form=form)
'''


