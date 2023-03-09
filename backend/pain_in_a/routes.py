import datetime
from app import app, db, bcrypt, jwt
from models import User, Physician, Patient, Undergoes, Appointment, Procedure, Medication, Prescribes, Nurse, Stay
from flask import request, make_response, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, current_user

from boto3 import session
from botocore.client import Config

from uuid import uuid4

ACCESS_ID = 'XXXXXXX'
SECRET_KEY = 'XXXXXXX'

# todo: natural join the tables in question

def sqlalchemy_row_to_dict(row):

    return { column.name:str( getattr(row, column.name) ) for column in row.__table__.columns }

UUID_RANGE_LIMIT = 1000000

@app.route('/user', methods=['POST', 'GET'])
def user():
    
    if request.method == 'POST':

        # getting the response from the form
        # @Chirag add these to the form

        email = request.form.get('email')
        role = request.form.get('role')
        password = request.form.get('password')
        name = request.form.get('name')
        position = request.form.get('position')
        ssn = request.form.get('ssn')

        # adding the new user

        unique_id = int(uuid4()) % UUID_RANGE_LIMIT
        user = User(
            id = unique_id
            , email = email
            , password = bcrypt.generate_password_hash(password)
            , role = role
            , name=name
            )
        
        # inserting user into db
        db.session.add(user)
        db.session.commit()

        # if doctor then also to be added
        # into the Physician table

        if role == 'Doctor':

            physician = Physician(
                EmployeeID = unique_id
                , Name = name
                , Position = position
                , SSN = ssn
            )

            db.session.add(physician)
            db.session.commit()

        return make_response(jsonify(
                {
                    "message": "User created"
                }
            ) , 201)
    
    # get all users in db
    users =  User.query.all()
    users = "Null" if users is None else [sqlalchemy_row_to_dict(user) for user in users]

    return make_response(jsonify(
            {
                "message": "Retreived all users"
                , "users": users
            }
        ), 200)

@app.route('/user/login', methods=['POST'])
def user_login():

    email = request.form.get('email')
    password = request.form.get('password')

    user = User.query.filter_by(email = email).first()

    if not user:

        return make_response(
            jsonify(
                {
                    "message": "Incorrect user"
                }
            ), 403
        )
    
    if bcrypt.check_password_hash(user.password, password):

        # create a token

        authenticate = create_access_token(identity = email)

        return make_response(

            jsonify({
                "Authenticate": authenticate
            }), 201
        )
    
    else:
        return make_response(
            jsonify(
                {
                    "message": "Incorrect password"
                }
            ), 403
        )

# @jwt.user_identity_loader
# def user_id(user):
#     return user.email

@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):

    identity = jwt_data['sub']
    return User.query.filter_by(email = identity).one_or_none()

@app.route('/token_user')
@jwt_required()
def token_user():

    #_user = get_jwt_identity()
    return jsonify(
        {
            "id": current_user.id
            , "email": current_user.email
            , "name": current_user.name
            , "role": current_user.role
        }
    )

@app.route('/patient', methods=['POST', 'GET'])
@jwt_required()
def patient():

    if request.method == 'POST':
        
        # @Chirag the forms
        ssn = request.form.get('SSN')
        name = request.form.get('Name')
        address = request.form.get('Address')
        phone = request.form.get('Phone')
        insurance_id = request.form.get('InsuranceID')
        pcp = request.form.get('PCP')
        gender = request.form.get('Gender')
        age = request.form.get('Age')

        patient = Patient(

            SSN = ssn
            , Name = name
            , Address = address
            , Phone = phone
            , InsuranceID = insurance_id
            , PCP = pcp
            , Gender = gender
            , Age = age
        )

        db.session.add(patient)
        db.session.commit()
        
        return make_response(jsonify(
                {
                    "message": "Patient created"
                }
            ) , 201)
    
    # get all patients in db
    patients = db.session.query(Patient, Physician).join(Physician, Physician.EmployeeID == Patient.PCP).all()
    patients = "Null" if patients is None else [(sqlalchemy_row_to_dict(patient[0]), sqlalchemy_row_to_dict(patient[1])) for patient in patients]

    return make_response(jsonify(
            {
                "message": "Retreived all patients"
                , "patients": patients
            }
        ), 200)

def get_medication(code):
    medication = db.session.query(Medication).filter(Medication.Code == code)
    return sqlalchemy_row_to_dict(medication[0])

@app.route('/patient/<int:ssn>')
#@jwt_required()
def patient_ssn(ssn):

    # getting all the patient information

    # getting the patient basic data
    patient = db.session.query(Patient, Physician
                               ).join(Physician, Patient.PCP == Physician.EmployeeID
                                      ).filter(Patient.SSN == ssn).first()
    if patient:
        patient = sqlalchemy_row_to_dict(patient[0]), sqlalchemy_row_to_dict(patient[1])
    else:
        return make_response(
            jsonify(
                {
                    "message": "Not found"
                }
            ), 404
        )

    # undergoes data
    undergoes = db.session.query(Undergoes, Physician, Procedure
                                 ).join(Physician, Undergoes.Physician == Physician.EmployeeID
                                        ).filter(Undergoes.Patient == ssn
                                 ).join(Procedure, Undergoes.Procedure == Procedure.Code
                                        ).filter(Undergoes.Patient == ssn)
    if undergoes:
        undergoes = [(sqlalchemy_row_to_dict(undergone[0]), sqlalchemy_row_to_dict(undergone[1]), sqlalchemy_row_to_dict(undergone[2])) for undergone in undergoes]
    # appointments
    appointments =  db.session.query(Appointment, Physician, Prescribes
                                     ).filter(Appointment.Patient == ssn
                                     ).filter(Appointment.Physician == Physician.EmployeeID
                                     ).outerjoin(Prescribes, Prescribes.Appointment == Appointment.AppointmentID)
    
    if appointments:
        appointments = [(sqlalchemy_row_to_dict(appointment[0]), sqlalchemy_row_to_dict(appointment[1]), get_medication(appointment[2].Medication) if appointment[2] != None else None) for appointment in appointments]

    # appointment data
    return make_response(
        jsonify(
            {
                "patient": patient
                , "undergoes": undergoes
                , "appointments": appointments
            }
        ), 200
    )

# @Shreya and @Chirag

@app.route('/patient/<int:ssn>/appointment', methods=['POST', 'GET'])
@jwt_required()
def patient_ssn_appointment(ssn):

    patient = Patient.query.filter_by(SSN = ssn).first()
    if not patient:
        return make_response(
            jsonify(
                {
                    "message": "Not found"
                }
            ), 404
        )
    if request.method == 'POST':
        # @Chirag the forms
        patient = ssn
        physician = request.form.get('physician')
        start = datetime.datetime.strptime(request.form.get('datetime'), "%Y-%m-%dT%H:%M:%S.%fZ")
        examinationroom = "cabin"
        appointment_id = Appointment.query.count() + 1
        nurses = Nurse.query.all()
        nurseid = None
        for nurse in nurses:
            nurseid = nurse.EmployeeID
            break
        appointment = Appointment(AppointmentID=appointment_id,
                                    Patient=patient,
                                    Physician=physician,
                                    Start=start,
                                    ExaminationRoom=examinationroom,
                                    PrepNurse=nurseid 
                                )
        db.session.add(appointment)
        db.session.commit()
        return make_response(jsonify(
                {
                    "message": "Appointment scheduled"
                }
            ) , 201)
    
    else:
        all_engagements = []
        physicians = Physician.query.all()
        for physician in physicians:
            engagements = []
            appointments = Appointment.query.filter_by(Physician = physician.EmployeeID).all()
            undergoes = Undergoes.query.filter_by(Physician = physician.EmployeeID).all()
            for appointment in appointments:
                engagements.append(appointment.Start)
            for undergo in undergoes:
                engagements.append(undergo.Date)
            physician_engagement =  {
                    'physician': physician.EmployeeID
                    ,'engagements':engagements
                }
            
            all_engagements.append(physician_engagement)
        return make_response(
            jsonify({
                "message":"All engagements retreived",
                "phsyicians":all_engagements
                
            }),200
        )

# @Shreya and @Chirag

@app.route('/patient/<int:ssn>/test', methods=['POST', 'GET'])
@jwt_required()
def patient_ssn_test(ssn):

    patient = Patient.query.filter_by(SSN = ssn).first()
    if not patient:
        return make_response(
            jsonify(
                {
                    "message": "Not found"
                }
            ), 404
        )
    if request.method == 'POST':
                # @Chirag the forms

        patient = ssn
        physician = request.form.get('physician')
        procedure = request.form.get('procedure')
        date = datetime.datetime.strptime(request.form.get('datetime'), "%Y-%m-%dT%H:%M:%S.%fZ")
        nurses = Nurse.query.all()
        nurseid = None
        for nurse in nurses:
            nurseid = nurse.EmployeeID
            break
        result = ""
        artifact = ""
        stays = Stay.query.all()
        stayid = -1
        for stay in stays:
            if stay.Patient == patient and stay.Start <= date and stay.End >= date:
                stayid = stay.StayID
                break

        if stayid == -1:
            return make_response(
            jsonify(
                {
                    "message": "Invalid test date"
                }
            ), 404
            )
        else:
            undergo = Undergoes(Patient=patient,
                                Procedure=procedure,
                                Stay=stayid,
                                Date=date,
                                Physician=physician,
                                AssistingNurse=nurseid,
                                Result=result,
                                Artifact=artifact)
            db.session.add(undergo)
            db.session.commit()
            return make_response(jsonify(
                {
                    "message": "Test scheduled"
                }
            ) , 201)
    else:
        all_engagements = []
        physicians = Physician.query.all()
        for physician in physicians:
            engagements = []
            appointments = Appointment.query.filter_by(Physician = physician.EmployeeID).all()
            undergoes = Undergoes.query.filter_by(Physician = physician.EmployeeID).all()
            for appointment in appointments:
                engagements.append(appointment.Start)
            for undergo in undergoes:
                engagements.append(undergo.Date)
            physician_engagement = {
                    "physician": physician.EmployeeID
                    ,"engagements":engagements
                }
            
            all_engagements.append(physician_engagement)
        return make_response(
            jsonify({
                "message":"All engagements retreived",
                "phsyicians":all_engagements
            }),200
        )

@app.route('/physician', methods=['POST', 'GET'])
@jwt_required()
def physician():

    # get all physicians in DB

    physicians = [sqlalchemy_row_to_dict(physician) for physician in Physician.query.all()]
    physicians = "Null" if physicians is None else physicians

    return make_response(jsonify(
            {
                "message": "Retreived all physicians"
                , "physicians": physicians
            }
        ), 200)

def get_prescriptions(appointment):

    prescriptions = Prescribes.query.filter_by(Appointment = appointment.AppointmentID)
    return "Null" if prescriptions is None else [sqlalchemy_row_to_dict(pres) for pres in prescriptions]

@app.route('/physician/<int:id>')
@jwt_required()
def physician_id(id):

    # get physician info (all)

    physician = sqlalchemy_row_to_dict(Physician.query.filter_by(EmployeeID = id).first())

    if not physician:
        return make_response(
            jsonify(
                {
                    "message": "Not found"
                }
            ), 404
        )
    
    # get the patient info from appointment
    
    appointments = Appointment.query.filter_by(Physician = physician["EmployeeID"])
    appointments = "Null" if appointments is None else [(sqlalchemy_row_to_dict(appointment), get_prescriptions(appointment)) for appointment in appointments]

    return make_response(jsonify(
            {
                "message": "Retreived all data"
                , "physician": physician
                , "appointments": appointments
            }
        ), 200)

@app.route('/physician/<int:id>/engagements')
@jwt_required()
def physician_engagements(id):

    # get physician schedule (basically all appointments)
    physicians = Physician.query.all()

    engagements = []
    appointments = Appointment.query.filter_by(Physician = id).all()
    undergoes = Undergoes.query.filter_by(Physician = id).all()
    for appointment in appointments:
        engagements.append(appointment.Start.isoformat())
    for undergo in undergoes:
        engagements.append(undergo.Date.isoformat())
    return make_response(
        jsonify({
            "message":"All engagements retreived",
            "engagements":engagements
            
        }),200
    )

@app.route('/procedure')
@jwt_required()
def procedure():

    # get all procedures
    procedures = Procedure.query.all()
    procedures = "Null" if procedures is None else [sqlalchemy_row_to_dict(procedure) for procedure in procedures]
    return make_response(jsonify(
            {
                "message": "Retreived all procedures"
                , "procedures": procedures
            }
        ), 200)

# @Shreya and @Chirag

@app.route('/procedure/<int:id>', methods=['PATCH'])
@jwt_required()
def procedure_id(id):
    procedure = Procedure.query.filter_by(Code = id)
    if not procedure:
        return make_response(
            jsonify(
                {
                    "message": "Not found"
                }
            ), 404
        )
    if request.method == 'PATCH':
        #@Chirag the forms
        file_name = request.form.get('file')
        patient = request.form.get('patient')
        procedure = id
        date = request.form.get('date')
        stay = request.form.get('stay')
        undergo = Undergoes.query.filter_by(Patient=patient,Stay=stay,Procedure=procedure,Date=date).first()
        if not undergo:
            return make_response(
            jsonify(
                {
                    "message": "Record Not found"
                }
            ), 404
        )
        session = session.Session()
        client = session.client('s3',
                        region_name='nyc3',
                        endpoint_url='https://nyc3.digitaloceanspaces.com',
                        aws_access_key_id=ACCESS_ID,
                        aws_secret_access_key=SECRET_KEY)

        dest_path = str(patient) + "/" + str(procedure) + "/" + str(stay) + "/" + date.strftime("%Y-%m-%d-%H:%M:%S") + "." + file_name.split('.',1)[1]
        client.upload_file(file_name, 'hello-spaces', dest_path)
        undergo.Artifact = dest_path
        undergo.Result = "Uploaded"
        db.session.commit()
        return make_response(
            jsonify(
                {
                    "message": "File uploaded",
                    "url": dest_path
                }
            ), 201
        )

@app.route('/medication')
@jwt_required()
def medication():

    # get all medications
    procedures = Medication.query.all()
    procedures = "Null" if procedures is None else [sqlalchemy_row_to_dict(procedure) for procedure in procedures]
    return make_response(jsonify(
            {
                "message": "Retreived all medication"
                , "medications": procedures
            }
        ), 200)

@app.route('/appointment/<int:id>', methods=['PATCH', 'GET'])
@jwt_required()
def appointment_id(id):
    # getting the appointment info
    appointment = Appointment.query.filter_by(AppointmentID = id).first()

    if not appointment:
        return make_response(
            jsonify(
                {
                    "message": "Not found"
                }
            ), 404
        )

    if request.method == 'PATCH':

        # patching a medication into an appointment
        # I am basically adding it to prescribes

        medication = request.form.get('medication')
        dose = request.form.get('dose')

        physician = appointment.Physician
        patient = appointment.Patient
        date = appointment.Start

        prescription = Prescribes(Physician = physician
                                  , Patient = patient
                                  , Date = date
                                  , Appointment = appointment.AppointmentID
                                  , Medication = medication
                                  , Dose = dose)
        
        db.session.add(prescription)
        db.session.commit()
        return make_response(
            jsonify({
                "message": "Patched medication, dose into Prescribes"
            }), 201
        )
    
    # getting the physician

    physician = Physician.query.filter_by(EmployeeID = appointment.Physician).first()
    physician = "Null" if physician is None else sqlalchemy_row_to_dict( physician )
    # getting the patient

    patient = Patient.query.filter_by(SSN = appointment.Patient).first()
    patient = "Null" if patient is None else sqlalchemy_row_to_dict( patient )
    
    return make_response(
        jsonify(
            {
                "appointment": sqlalchemy_row_to_dict(appointment)
                , "physician": physician
                , "patient": patient
            }
        ), 200
    )

@app.route('/notify')
def notify():

    # todo

    # send mails
    return 'NOTIFY MAILS'
