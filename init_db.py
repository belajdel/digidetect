#!/usr/bin/env python3
"""
Script d'initialisation de la base de données
Crée les tables avec les nouveaux champs et un utilisateur admin par défaut
"""

from app_with_db import app
from models import db, User, SystemStats
from datetime import datetime

def init_database():
    """Initialise la base de données avec les nouvelles tables et données par défaut"""
    
    print("🚀 Initialisation de la base de données...")
    
    with app.app_context():
        # Supprimer toutes les tables existantes
        print("📝 Suppression des anciennes tables...")
        db.drop_all()
        
        # Créer toutes les tables avec les nouveaux champs
        print("🏗️  Création des nouvelles tables...")
        db.create_all()
        
        # Créer un utilisateur admin par défaut
        print("👤 Création de l'utilisateur admin par défaut...")
        admin_user = User(
            username='admin',
            role='admin',
            is_approved=True,
            full_name='Administrateur Système',
            email='admin@postal-detector.com',
            department='Administration',
            phone='+216 XX XXX XXX',
            address='Bureau Principal',
            bio='Compte administrateur principal du système',
            created_at=datetime.now(),
            profile_updated_at=datetime.now()
        )
        admin_user.set_password('admin123')  # Mot de passe par défaut
        
        # Créer un utilisateur test
        print("👤 Création d'un utilisateur test...")
        test_user = User(
            username='user1',
            role='user',
            is_approved=True,
            full_name='Utilisateur Test',
            email='user@postal-detector.com',
            department='Test',
            phone='+216 XX XXX XXX',
            address='Adresse de test',
            bio='Compte utilisateur de test',
            created_at=datetime.now(),
            profile_updated_at=datetime.now()
        )
        test_user.set_password('user123')  # Mot de passe par défaut
        
        # Créer les statistiques système
        print("📊 Initialisation des statistiques système...")
        system_stats = SystemStats(
            start_time=datetime.now(),
            total_detections=0,
            unique_codes_count=0,
            last_updated=datetime.now()
        )
        
        # Ajouter tous les objets à la session
        db.session.add(admin_user)
        db.session.add(test_user)
        db.session.add(system_stats)
        
        # Sauvegarder en base de données
        db.session.commit()
        
        print("✅ Base de données initialisée avec succès !")
        print()
        print("📋 COMPTES CRÉÉS :")
        print("   👨‍💼 Admin:")
        print("      Nom d'utilisateur: admin")
        print("      Mot de passe: admin123")
        print("      Rôle: Administrateur")
        print()
        print("   👤 Utilisateur test:")
        print("      Nom d'utilisateur: user1")
        print("      Mot de passe: user123")
        print("      Rôle: Utilisateur standard")
        print()
        print("🌐 Vous pouvez maintenant démarrer l'application et vous connecter !")

if __name__ == "__main__":
    init_database() 