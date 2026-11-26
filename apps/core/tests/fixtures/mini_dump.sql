-- Jeu de données FICTIF pour les tests automatiques (structure identique à l'original, aucune donnée réelle).
-- Cas couverts : apostrophes (\' et ''), antislash, retour à la ligne, point-virgule et -- dans un texte, NULL, chaîne vide,
-- accents, séquence déjà corrompue (conservée telle quelle), décimaux négatifs, ENUM accentués, horodatages.

SET SQL_MODE="NO_AUTO_VALUE_ON_ZERO";

CREATE TABLE `categorie` (
  `id_categorie` int(11) NOT NULL,
  `nom_categorie` varchar(50) NOT NULL,
  UNIQUE KEY `id_categorie` (`id_categorie`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

INSERT INTO `categorie` (`id_categorie`, `nom_categorie`) VALUES
(1, 'Optique générale'),
(2, 'Lunettes d\'enfant'),
(30, 'Catégorie ''test''');

CREATE TABLE `client` (
  `id_client` int(100) NOT NULL,
  `nom_client` varchar(100) NOT NULL,
  UNIQUE KEY `id_client` (`id_client`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

CREATE TABLE `fournisseur` (
  `idfournisseur` int(11) NOT NULL auto_increment,
  `nom` varchar(100) default NULL,
  `responsable` varchar(100) default NULL,
  `adresse` varchar(200) default NULL,
  `ville` varchar(100) default NULL,
  `telephone` varchar(20) default NULL,
  `email` varchar(100) default NULL,
  PRIMARY KEY  (`idfournisseur`)
) ENGINE=InnoDB  DEFAULT CHARSET=latin1 AUTO_INCREMENT=8 ;

INSERT INTO `fournisseur` (`idfournisseur`, `nom`, `responsable`, `adresse`, `ville`, `telephone`, `email`) VALUES
(1, 'Fournisseur Alpha', 'Jean Dupont', '1 rue de la Paix', 'Paris', '0102030405', 'alpha@example.com'),
(2, 'Société Béta', NULL, NULL, 'Lyon', NULL, NULL),
(7, 'Ça-va Ltd', 'Zoë', '', 'Genève', '', 'z@example.com');

CREATE TABLE `lentille` (
  `idlentille` varchar(10) NOT NULL,
  `nom` varchar(100) NOT NULL,
  `marque` varchar(5) default NULL,
  `type` enum('journalière','hebdomadaire','mensuelle','annuelle') default NULL,
  `materiau` varchar(50) default NULL,
  `correction` enum('sphérique','torique','multifocale') default NULL,
  `couleur` varchar(50) default NULL,
  `diametre` decimal(4,1) default NULL,
  `rayon_courbure` decimal(4,2) default NULL,
  `puissance_min` decimal(5,2) default NULL,
  `puissance_max` decimal(5,2) default NULL,
  `prix` decimal(10,2) default NULL,
  `stock` int(11) default '0',
  `idfournisseur` int(11) default NULL,
  `description` varchar(255) default NULL,
  PRIMARY KEY  (`idlentille`),
  KEY `idmarque` (`marque`),
  KEY `idfournisseur` (`idfournisseur`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

INSERT INTO `lentille` (`idlentille`, `nom`, `marque`, `type`, `materiau`, `correction`, `couleur`, `diametre`, `rayon_courbure`, `puissance_min`, `puissance_max`, `prix`, `stock`, `idfournisseur`, `description`) VALUES
('LT001', 'Acuvue', 'CK', 'hebdomadaire', 'Silicone-hydrogel', 'sphérique', 'transparent', 14.0, 8.40, -6.00, 4.00, 180.00, 50, 1, 'Lentille d\'essai'),
('LT002', 'Air Night', 'OK', 'journalière', NULL, 'torique', NULL, 13.8, 8.60, -8.00, 6.00, 220.00, 40, 2, NULL);

CREATE TABLE `marque` (
  `idmarque` varchar(10) NOT NULL,
  `nom` varchar(100) default NULL,
  `pays` varchar(100) default NULL,
  `description` varchar(255) default NULL,
  PRIMARY KEY  (`idmarque`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

INSERT INTO `marque` (`idmarque`, `nom`, `pays`, `description`) VALUES
('M001', 'Marque Un', 'France', 'Description avec accent é et apostrophe d\'or'),
('M002', 'Brand Two', 'USA', NULL),
('M003', 'Corrompue', 'Italie', 'Marque cï¿½lï¿½bre'),
('M004', 'Chemin', 'Pays', 'C:\\opti\\fichier\nsuite ; avec point-virgule -- et tirets');

CREATE TABLE `monture` (
  `idmonture` int(11) NOT NULL auto_increment,
  `reference` varchar(50) NOT NULL,
  `modele` varchar(100) default NULL,
  `couleur` varchar(50) default NULL,
  `materiau` varchar(50) default NULL,
  `genre` enum('homme','femme','enfant','mixte') default NULL,
  `prix` decimal(10,2) default NULL,
  `stock` int(11) default '0',
  `idmarque` varchar(10) default NULL,
  `idfournisseur` int(11) default NULL,
  `idcategorie` varchar(10) default NULL,
  `description` varchar(255) default NULL,
  PRIMARY KEY  (`idmonture`),
  KEY `idmarque` (`idmarque`),
  KEY `idfournisseur` (`idfournisseur`),
  KEY `idcategorie` (`idcategorie`)
) ENGINE=InnoDB  DEFAULT CHARSET=latin1 AUTO_INCREMENT=16 ;

INSERT INTO `monture` (`idmonture`, `reference`, `modele`, `couleur`, `materiau`, `genre`, `prix`, `stock`, `idmarque`, `idfournisseur`, `idcategorie`, `description`) VALUES
(11, 'REF011', 'Modèle Un', 'Noir', 'Acï¿½tate', 'femme', 2800.00, 6, 'CH', 2, 'CAT07', 'Monture élégante'),
(12, 'REF012', NULL, NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL, NULL),
(15, 'REF015', 'Modèle Cinq', 'Bleu', 'Métal', 'mixte', 99.90, NULL, 'M001', 1, 'CAT01', '');

CREATE TABLE `ordonnance` (
  `idordonnance` int(11) NOT NULL auto_increment,
  `idpatient` int(11) NOT NULL,
  `date_ordonnance` date NOT NULL,
  `medecin` varchar(100) default NULL,
  `od_sphere` decimal(5,2) default NULL,
  `od_cylindre` decimal(5,2) default NULL,
  `od_axe` int(3) default NULL,
  `od_addition` decimal(4,2) default NULL,
  `og_sphere` decimal(5,2) default NULL,
  `og_cylindre` decimal(5,2) default NULL,
  `og_axe` int(3) default NULL,
  `og_addition` decimal(4,2) default NULL,
  `ecart_pupillaire_vl` decimal(4,1) default NULL,
  `ecart_pupillaire_vp` decimal(4,1) default NULL,
  `idmonture` int(11) default NULL,
  `idverre_od` varchar(10) default NULL,
  `idverre_og` varchar(10) default NULL,
  `idlentille` varchar(10) default NULL,
  `remarques` text,
  `date_creation` timestamp NOT NULL default CURRENT_TIMESTAMP,
  PRIMARY KEY  (`idordonnance`),
  KEY `idpatient` (`idpatient`),
  KEY `idmonture` (`idmonture`),
  KEY `idverre_od` (`idverre_od`),
  KEY `idverre_og` (`idverre_og`),
  KEY `idlentille` (`idlentille`)
) ENGINE=InnoDB  DEFAULT CHARSET=latin1 AUTO_INCREMENT=3 ;

INSERT INTO `ordonnance` (`idordonnance`, `idpatient`, `date_ordonnance`, `medecin`, `od_sphere`, `od_cylindre`, `od_axe`, `od_addition`, `og_sphere`, `og_cylindre`, `og_axe`, `og_addition`, `ecart_pupillaire_vl`, `ecart_pupillaire_vp`, `idmonture`, `idverre_od`, `idverre_og`, `idlentille`, `remarques`, `date_creation`) VALUES
(1, 1, '2026-01-15', 'Dr. Test', -2.50, -0.75, 180, NULL, -3.00, -0.50, 175, NULL, 64.0, 61.0, 11, 'ES19', 'ES19', NULL, 'Remarque', '2026-04-24 11:47:17'),
(2, 2, '2026-02-03', NULL, 1.25, NULL, NULL, 2.00, 1.50, NULL, NULL, 2.00, 62.0, 59.5, NULL, NULL, NULL, 'LT001', 'Lentilles', '2026-04-24 11:47:17');

CREATE TABLE `patient` (
  `id` int(11) NOT NULL auto_increment,
  `nom` varchar(50) NOT NULL,
  `prenom` varchar(50) NOT NULL,
  `date_naissance` date default NULL,
  `sexe` enum('M','F','Autre') default NULL,
  `telephone` varchar(20) default NULL,
  `email` varchar(100) default NULL,
  `adresse` text,
  `code_postal` varchar(10) default NULL,
  `ville` varchar(50) default NULL,
  `numero_securite_sociale` varchar(15) default NULL,
  `nom_mutuelle` varchar(100) default NULL,
  `numero_adherent_mutuelle` varchar(50) default NULL,
  `date_creation` timestamp NOT NULL default CURRENT_TIMESTAMP,
  `notes_importantes` text,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB  DEFAULT CHARSET=latin1 AUTO_INCREMENT=4 ;

INSERT INTO `patient` (`id`, `nom`, `prenom`, `date_naissance`, `sexe`, `telephone`, `email`, `adresse`, `code_postal`, `ville`, `numero_securite_sociale`, `nom_mutuelle`, `numero_adherent_mutuelle`, `date_creation`, `notes_importantes`) VALUES
(1, 'Durand', 'Claire', '1992-05-14', 'M', '0600000001', 'a@example.com', NULL, NULL, 'Casablanca', NULL, 'CNSS', '123456789', '2026-04-24 09:41:53', NULL),
(2, 'Élise', 'Zoë', '2001-11-23', 'F', NULL, NULL, '12 rue d\'Alger\nBâtiment 3', '20000', 'Rabat', NULL, NULL, NULL, '2026-04-24 09:41:53', 'Allergie à vérifier'),
(3, 'Sans Date', 'Test', NULL, 'Autre', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-11-03 23:59:59', NULL);

CREATE TABLE `verre` (
  `code_verre` varchar(10) NOT NULL,
  `nom` varchar(100) NOT NULL,
  `type_verre` varchar(50) NOT NULL,
  `indice` varchar(10) NOT NULL,
  `traitement` varchar(50) default NULL,
  `prix` decimal(10,2) NOT NULL,
  `code_fournisseur` varchar(10) default NULL,
  `description` text,
  PRIMARY KEY  (`code_verre`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

INSERT INTO `verre` (`code_verre`, `nom`, `type_verre`, `indice`, `traitement`, `prix`, `code_fournisseur`, `description`) VALUES
('ES15', 'Essilor Standard', 'Simple foyer', '1.50', 'Antireflet', 350.00, 'ES', 'Verre simple vision'),
('HO16', 'Hoya Progressif', 'Progressif', '1.60', NULL, 520.50, NULL, NULL);
