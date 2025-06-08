"""
Profile Update Forms
Handles form validation for user profile updates
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, EmailField, TelField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp, ValidationError
from wtforms.widgets import TextArea
from models import User, db

class ProfileUpdateForm(FlaskForm):
    """Form for updating user profile information"""
    
    full_name = StringField(
        'Nom Complet', 
        validators=[
            DataRequired(message="Le nom complet est requis"),
            Length(min=2, max=100, message="Le nom doit contenir entre 2 et 100 caractères")
        ],
        render_kw={
            'placeholder': 'Entrez votre nom complet',
            'class': 'form-control'
        }
    )
    
    email = EmailField(
        'Adresse Email',
        validators=[
            DataRequired(message="L'adresse email est requise"),
            Email(message="Veuillez entrer une adresse email valide"),
            Length(max=120, message="L'email ne peut pas dépasser 120 caractères")
        ],
        render_kw={
            'placeholder': 'exemple@email.com',
            'class': 'form-control'
        }
    )
    
    department = StringField(
        'Département',
        validators=[
            Optional(),
            Length(max=50, message="Le département ne peut pas dépasser 50 caractères")
        ],
        render_kw={
            'placeholder': 'Votre département',
            'class': 'form-control'
        }
    )
    
    phone = TelField(
        'Numéro de Téléphone',
        validators=[
            Optional(),
            Length(max=20, message="Le numéro de téléphone ne peut pas dépasser 20 caractères"),
            Regexp(
                r'^[\+]?[1-9][\d\s\-\(\)]{7,}$',
                message="Veuillez entrer un numéro de téléphone valide"
            )
        ],
        render_kw={
            'placeholder': '+216 XX XXX XXX',
            'class': 'form-control'
        }
    )
    
    address = TextAreaField(
        'Adresse',
        validators=[
            Optional(),
            Length(max=500, message="L'adresse ne peut pas dépasser 500 caractères")
        ],
        render_kw={
            'placeholder': 'Votre adresse complète',
            'class': 'form-control',
            'rows': 3
        }
    )
    
    bio = TextAreaField(
        'Biographie',
        validators=[
            Optional(),
            Length(max=1000, message="La biographie ne peut pas dépasser 1000 caractères")
        ],
        render_kw={
            'placeholder': 'Parlez-nous de vous...',
            'class': 'form-control',
            'rows': 4
        }
    )
    
    submit = SubmitField(
        'Mettre à jour le profil',
        render_kw={
            'class': 'btn btn-primary btn-lg'
        }
    )
    
    def __init__(self, current_user, *args, **kwargs):
        super(ProfileUpdateForm, self).__init__(*args, **kwargs)
        self.current_user = current_user
    
    def validate_email(self, field):
        """Custom validation to ensure email uniqueness"""
        # Check if email is changing
        if field.data != self.current_user.email:
            # Check if email already exists for another user
            existing_user = User.query.filter(
                User.email == field.data,
                User.id != self.current_user.id
            ).first()
            
            if existing_user:
                raise ValidationError('Cette adresse email est déjà utilisée par un autre utilisateur.')

class PasswordChangeForm(FlaskForm):
    """Form for changing user password within profile"""
    
    current_password = StringField(
        'Mot de passe actuel',
        validators=[
            DataRequired(message="Le mot de passe actuel est requis")
        ],
        render_kw={
            'type': 'password',
            'placeholder': 'Entrez votre mot de passe actuel',
            'class': 'form-control'
        }
    )
    
    new_password = StringField(
        'Nouveau mot de passe',
        validators=[
            DataRequired(message="Le nouveau mot de passe est requis"),
            Length(min=6, message="Le mot de passe doit contenir au moins 6 caractères")
        ],
        render_kw={
            'type': 'password',
            'placeholder': 'Entrez le nouveau mot de passe',
            'class': 'form-control'
        }
    )
    
    confirm_password = StringField(
        'Confirmer le mot de passe',
        validators=[
            DataRequired(message="La confirmation du mot de passe est requise")
        ],
        render_kw={
            'type': 'password',
            'placeholder': 'Confirmez le nouveau mot de passe',
            'class': 'form-control'
        }
    )
    
    submit = SubmitField(
        'Changer le mot de passe',
        render_kw={
            'class': 'btn btn-warning btn-lg'
        }
    )
    
    def __init__(self, current_user, *args, **kwargs):
        super(PasswordChangeForm, self).__init__(*args, **kwargs)
        self.current_user = current_user
    
    def validate_current_password(self, field):
        """Validate that the current password is correct"""
        if not self.current_user.check_password(field.data):
            raise ValidationError('Le mot de passe actuel est incorrect.')
    
    def validate_confirm_password(self, field):
        """Validate that password confirmation matches"""
        if field.data != self.new_password.data:
            raise ValidationError('Les mots de passe ne correspondent pas.')

class AdminUserEditForm(FlaskForm):
    """Form for administrators to edit user information"""
    
    username = StringField(
        'Nom d\'utilisateur',
        validators=[
            DataRequired(message="Le nom d'utilisateur est requis"),
            Length(min=3, max=80, message="Le nom d'utilisateur doit contenir entre 3 et 80 caractères")
        ],
        render_kw={
            'placeholder': 'Nom d\'utilisateur',
            'class': 'form-control'
        }
    )
    
    full_name = StringField(
        'Nom complet',
        validators=[
            Optional(),
            Length(max=100, message="Le nom complet ne peut pas dépasser 100 caractères")
        ],
        render_kw={
            'placeholder': 'Nom complet de l\'utilisateur',
            'class': 'form-control'
        }
    )
    
    email = EmailField(
        'Adresse email',
        validators=[
            Optional(),
            Email(message="Veuillez entrer une adresse email valide"),
            Length(max=120, message="L'email ne peut pas dépasser 120 caractères")
        ],
        render_kw={
            'placeholder': 'exemple@email.com',
            'class': 'form-control'
        }
    )
    
    department = StringField(
        'Département',
        validators=[
            Optional(),
            Length(max=50, message="Le département ne peut pas dépasser 50 caractères")
        ],
        render_kw={
            'placeholder': 'Département de l\'utilisateur',
            'class': 'form-control'
        }
    )
    
    phone = TelField(
        'Numéro de téléphone',
        validators=[
            Optional(),
            Length(max=20, message="Le numéro de téléphone ne peut pas dépasser 20 caractères"),
            Regexp(
                r'^[\+]?[1-9][\d\s\-\(\)]{7,}$',
                message="Veuillez entrer un numéro de téléphone valide"
            )
        ],
        render_kw={
            'placeholder': '+216 XX XXX XXX',
            'class': 'form-control'
        }
    )
    
    address = TextAreaField(
        'Adresse',
        validators=[
            Optional(),
            Length(max=500, message="L'adresse ne peut pas dépasser 500 caractères")
        ],
        render_kw={
            'placeholder': 'Adresse complète',
            'class': 'form-control',
            'rows': 3
        }
    )
    
    bio = TextAreaField(
        'Biographie',
        validators=[
            Optional(),
            Length(max=1000, message="La biographie ne peut pas dépasser 1000 caractères")
        ],
        render_kw={
            'placeholder': 'Informations supplémentaires...',
            'class': 'form-control',
            'rows': 4
        }
    )
    
    role = SelectField(
        'Rôle',
        choices=[
            ('user', 'Utilisateur standard'),
            ('admin', 'Administrateur')
        ],
        validators=[
            DataRequired(message="Le rôle est requis")
        ],
        render_kw={
            'class': 'form-select'
        }
    )
    
    is_approved = SelectField(
        'Statut du compte',
        choices=[
            ('1', 'Approuvé'),
            ('0', 'En attente d\'approbation')
        ],
        validators=[
            DataRequired(message="Le statut du compte est requis")
        ],
        render_kw={
            'class': 'form-select'
        }
    )
    
    submit = SubmitField(
        'Mettre à jour l\'utilisateur',
        render_kw={
            'class': 'btn btn-primary btn-lg'
        }
    )
    
    def __init__(self, current_user_id, *args, **kwargs):
        super(AdminUserEditForm, self).__init__(*args, **kwargs)
        self.current_user_id = current_user_id
    
    def validate_username(self, field):
        """Custom validation to ensure username uniqueness"""
        # Check if username already exists for another user
        existing_user = User.query.filter(
            User.username == field.data,
            User.id != self.current_user_id
        ).first()
        
        if existing_user:
            raise ValidationError('Ce nom d\'utilisateur est déjà utilisé par un autre utilisateur.')
    
    def validate_email(self, field):
        """Custom validation to ensure email uniqueness if provided"""
        if field.data:  # Only validate if email is provided
            # Check if email already exists for another user
            existing_user = User.query.filter(
                User.email == field.data,
                User.id != self.current_user_id
            ).first()
            
            if existing_user:
                raise ValidationError('Cette adresse email est déjà utilisée par un autre utilisateur.')

class AdminUserAddForm(FlaskForm):
    """Form for administrators to add new users"""
    
    username = StringField(
        'Nom d\'utilisateur',
        validators=[
            DataRequired(message="Le nom d'utilisateur est requis"),
            Length(min=3, max=80, message="Le nom d'utilisateur doit contenir entre 3 et 80 caractères")
        ],
        render_kw={
            'placeholder': 'Nom d\'utilisateur unique',
            'class': 'form-control'
        }
    )
    
    password = StringField(
        'Mot de passe',
        validators=[
            DataRequired(message="Le mot de passe est requis"),
            Length(min=6, message="Le mot de passe doit contenir au moins 6 caractères")
        ],
        render_kw={
            'type': 'password',
            'placeholder': 'Mot de passe sécurisé',
            'class': 'form-control'
        }
    )
    
    confirm_password = StringField(
        'Confirmer le mot de passe',
        validators=[
            DataRequired(message="La confirmation du mot de passe est requise")
        ],
        render_kw={
            'type': 'password',
            'placeholder': 'Confirmez le mot de passe',
            'class': 'form-control'
        }
    )
    
    full_name = StringField(
        'Nom complet',
        validators=[
            Optional(),
            Length(max=100, message="Le nom complet ne peut pas dépasser 100 caractères")
        ],
        render_kw={
            'placeholder': 'Nom complet de l\'utilisateur',
            'class': 'form-control'
        }
    )
    
    email = EmailField(
        'Adresse email',
        validators=[
            Optional(),
            Email(message="Veuillez entrer une adresse email valide"),
            Length(max=120, message="L'email ne peut pas dépasser 120 caractères")
        ],
        render_kw={
            'placeholder': 'exemple@email.com',
            'class': 'form-control'
        }
    )
    
    department = StringField(
        'Département',
        validators=[
            Optional(),
            Length(max=50, message="Le département ne peut pas dépasser 50 caractères")
        ],
        render_kw={
            'placeholder': 'Département de l\'utilisateur',
            'class': 'form-control'
        }
    )
    
    phone = TelField(
        'Numéro de téléphone',
        validators=[
            Optional(),
            Length(max=20, message="Le numéro de téléphone ne peut pas dépasser 20 caractères"),
            Regexp(
                r'^[\+]?[1-9][\d\s\-\(\)]{7,}$',
                message="Veuillez entrer un numéro de téléphone valide"
            )
        ],
        render_kw={
            'placeholder': '+216 XX XXX XXX',
            'class': 'form-control'
        }
    )
    
    address = TextAreaField(
        'Adresse',
        validators=[
            Optional(),
            Length(max=500, message="L'adresse ne peut pas dépasser 500 caractères")
        ],
        render_kw={
            'placeholder': 'Adresse complète',
            'class': 'form-control',
            'rows': 3
        }
    )
    
    bio = TextAreaField(
        'Biographie',
        validators=[
            Optional(),
            Length(max=1000, message="La biographie ne peut pas dépasser 1000 caractères")
        ],
        render_kw={
            'placeholder': 'Informations supplémentaires...',
            'class': 'form-control',
            'rows': 4
        }
    )
    
    role = SelectField(
        'Rôle',
        choices=[
            ('user', 'Utilisateur standard'),
            ('admin', 'Administrateur')
        ],
        validators=[
            DataRequired(message="Le rôle est requis")
        ],
        render_kw={
            'class': 'form-select'
        }
    )
    
    is_approved = SelectField(
        'Statut du compte',
        choices=[
            ('1', 'Approuvé'),
            ('0', 'En attente d\'approbation')
        ],
        validators=[
            DataRequired(message="Le statut du compte est requis")
        ],
        render_kw={
            'class': 'form-select'
        },
        default='1'
    )
    
    submit = SubmitField(
        'Ajouter l\'utilisateur',
        render_kw={
            'class': 'btn btn-success btn-lg'
        }
    )
    
    def validate_username(self, field):
        """Custom validation to ensure username uniqueness"""
        existing_user = User.query.filter_by(username=field.data).first()
        if existing_user:
            raise ValidationError('Ce nom d\'utilisateur est déjà utilisé.')
    
    def validate_email(self, field):
        """Custom validation to ensure email uniqueness if provided"""
        if field.data:  # Only validate if email is provided
            existing_user = User.query.filter_by(email=field.data).first()
            if existing_user:
                raise ValidationError('Cette adresse email est déjà utilisée.')
    
    def validate_confirm_password(self, field):
        """Validate that password confirmation matches"""
        if field.data != self.password.data:
            raise ValidationError('Les mots de passe ne correspondent pas.') 