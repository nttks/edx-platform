-- MySQL dump 10.13  Distrib 5.6.30, for debian-linux-gnu (x86_64)
--
-- Host: localhost    Database: edxtest
-- ------------------------------------------------------
-- Server version	5.6.30-0ubuntu0.14.04.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Dumping data for table `django_migrations`
--

LOCK TABLES `django_migrations` WRITE;
/*!40000 ALTER TABLE `django_migrations` DISABLE KEYS */;
INSERT INTO `django_migrations` VALUES (1,'contenttypes','0001_initial','2018-08-22 03:15:23.576562'),(2,'auth','0001_initial','2018-08-22 03:15:24.025521'),(3,'admin','0001_initial','2018-08-22 03:15:24.152194'),(4,'assessment','0001_initial','2018-08-22 03:15:27.605905'),(5,'assessment','0002_staffworkflow','2018-08-22 03:15:27.733146'),(6,'contenttypes','0002_remove_content_type_name','2018-08-22 03:15:27.906254'),(7,'auth','0002_alter_permission_name_max_length','2018-08-22 03:15:27.981297'),(8,'auth','0003_alter_user_email_max_length','2018-08-22 03:15:28.054066'),(9,'auth','0004_alter_user_username_opts','2018-08-22 03:15:28.092100'),(10,'auth','0005_alter_user_last_login_null','2018-08-22 03:15:28.156217'),(11,'auth','0006_require_contenttypes_0002','2018-08-22 03:15:28.161208'),(12,'branding','0001_initial','2018-08-22 03:15:28.344895'),(13,'bulk_email','0001_initial','2018-08-22 03:15:28.708517'),(14,'bulk_email','0002_data__load_course_email_template','2018-08-22 03:15:28.752349'),(15,'instructor_task','0001_initial','2018-08-22 03:15:28.919589'),(16,'certificates','0001_initial','2018-08-22 03:15:30.089821'),(17,'certificates','0002_data__certificatehtmlviewconfiguration_data','2018-08-22 03:15:30.112886'),(18,'certificates','0003_data__default_modes','2018-08-22 03:15:30.147591'),(19,'certificates','0004_certificategenerationhistory','2018-08-22 03:15:30.316763'),(20,'certificates','0005_auto_20151208_0801','2018-08-22 03:15:30.408390'),(21,'certificates','0006_auto_20170810_1536','2018-08-22 03:15:30.645728'),(22,'commerce','0001_data__add_ecommerce_service_user','2018-08-22 03:15:30.675635'),(23,'cors_csrf','0001_initial','2018-08-22 03:15:30.813158'),(24,'course_action_state','0001_initial','2018-08-22 03:15:31.144917'),(25,'course_global','0001_initial','2018-08-22 03:15:31.189744'),(26,'course_groups','0001_initial','2018-08-22 03:15:32.462400'),(27,'course_modes','0001_initial','2018-08-22 03:15:32.601052'),(28,'course_modes','0002_coursemode_expiration_datetime_is_explicit','2018-08-22 03:15:32.663146'),(29,'course_modes','0003_auto_20151113_1443','2018-08-22 03:15:32.697128'),(30,'course_modes','0004_auto_20151113_1457','2018-08-22 03:15:32.876756'),(31,'course_modes','0005_auto_20161205_1514','2018-08-22 03:15:32.988266'),(32,'course_overviews','0001_initial','2018-08-22 03:15:33.110573'),(33,'course_overviews','0002_add_course_catalog_fields','2018-08-22 03:15:33.385526'),(34,'course_overviews','0003_courseoverviewgeneratedhistory','2018-08-22 03:15:33.428344'),(35,'course_overviews','0004_courseoverview_org','2018-08-22 03:15:33.490348'),(36,'course_overviews','0005_delete_courseoverviewgeneratedhistory','2018-08-22 03:15:33.519096'),(37,'course_structures','0001_initial','2018-08-22 03:15:33.565825'),(38,'courseware','0001_initial','2018-08-22 03:15:37.394595'),(39,'credit','0001_initial','2018-08-22 03:15:39.082874'),(40,'dark_lang','0001_initial','2018-08-22 03:15:39.302141'),(41,'dark_lang','0002_data__enable_on_install','2018-08-22 03:15:39.331599'),(42,'default','0001_initial','2018-08-22 03:15:39.946071'),(43,'default','0002_add_related_name','2018-08-22 03:15:40.163823'),(44,'default','0003_alter_email_max_length','2018-08-22 03:15:40.235828'),(45,'django_comment_common','0001_initial','2018-08-22 03:15:40.851965'),(46,'django_notify','0001_initial','2018-08-22 03:15:41.926567'),(47,'django_openid_auth','0001_initial','2018-08-22 03:15:42.265456'),(48,'edx_proctoring','0001_initial','2018-08-22 03:15:46.150314'),(49,'edxval','0001_initial','2018-08-22 03:15:46.915971'),(50,'edxval','0002_data__default_profiles','2018-08-22 03:15:46.956896'),(51,'embargo','0001_initial','2018-08-22 03:15:48.078786'),(52,'embargo','0002_data__add_countries','2018-08-22 03:15:48.523649'),(53,'external_auth','0001_initial','2018-08-22 03:15:49.183626'),(54,'ga_organization','0001_initial','2018-08-22 03:15:49.558144'),(55,'ga_contract','0001_initial','2018-08-22 03:15:51.074146'),(56,'ga_contract','0002_contractauth','2018-08-22 03:15:51.460080'),(57,'ga_contract','0003_contractauth_send_mail','2018-08-22 03:15:51.803118'),(58,'ga_contract','0004_contract_register_type','2018-08-22 03:15:52.178793'),(59,'ga_achievement','0001_initial','2018-08-22 03:15:52.982366'),(60,'ga_achievement','0002_submissionreminderbatchstatus','2018-08-22 03:15:54.852052'),(61,'ga_advanced_course','0001_initial','2018-08-22 03:15:55.160579'),(62,'ga_advanced_course','0002_auto_20161205_1605','2018-08-22 03:15:55.421073'),(63,'ga_contract','0005_contractoption','2018-08-22 03:15:55.803731'),(64,'ga_contract','0006_contractoption_send_submission_reminder','2018-08-22 03:15:56.140435'),(65,'ga_invitation','0001_initial','2018-08-22 03:15:58.014759'),(66,'ga_contract_operation','0001_initial','2018-08-22 03:15:59.603868'),(67,'ga_contract_operation','0002_auto_20170330_1046','2018-08-22 03:16:00.704083'),(68,'ga_contract_operation','0003_contract_oeration_bulkoperation','2018-08-22 03:16:03.352010'),(69,'ga_contract_operation','0004_contractremindermail','2018-08-22 03:16:04.707763'),(70,'ga_contract_operation','0005_additionalinfoupdatetasktarget','2018-08-22 03:16:05.199632'),(71,'ga_contract_operation','0006_studentmemberregistertasktarget','2018-08-22 03:16:05.703295'),(72,'ga_course_overviews','0001_initial','2018-08-22 03:16:05.809100'),(73,'ga_course_overviews','0002_auto_20161018_1117','2018-08-22 03:16:06.049362'),(74,'ga_course_overviews','0003_auto_20161129_1425','2018-08-22 03:16:06.373043'),(75,'ga_course_overviews','0004_courseoverviewextra_custom_logo','2018-08-22 03:16:06.457116'),(76,'ga_diagnosis','0001_initial','2018-08-22 03:16:08.071493'),(77,'ga_login','0001_initial','2018-08-22 03:16:08.619042'),(78,'ga_manager','0001_initial','2018-08-22 03:16:10.023388'),(79,'ga_manager','0002_data__default_manager_permission','2018-08-22 03:16:10.071870'),(80,'ga_manager','0003_data__update_manager_permission','2018-08-22 03:16:10.112074'),(81,'ga_optional','0001_initial','2018-08-22 03:16:12.172370'),(82,'ga_optional','0002_add_custom_logo_url_table','2018-08-22 03:16:12.577359'),(83,'ga_optional','0003_dashboardoptionalconfiguration','2018-08-22 03:16:13.050912'),(84,'ga_optional','0004_useroptionalconfiguration','2018-08-22 03:16:13.560012'),(85,'ga_optional','0005_courseoptionalconfiguration_add_choices','2018-08-22 03:16:13.980154'),(86,'ga_optional','0006_library_option','2018-08-22 03:16:14.403764'),(87,'ga_optional','0007_progress_restriction','2018-08-22 03:16:14.832914'),(88,'ga_optional','0008_ora2_video_upload_option','2018-08-22 03:16:15.259744'),(89,'ga_ratelimitbackend','0001_initial','2018-08-22 03:16:15.325474'),(90,'student','0001_initial','2018-08-22 03:16:32.129059'),(91,'shoppingcart','0001_initial','2018-08-22 03:16:46.877112'),(92,'shoppingcart','0002_auto_20151208_1034','2018-08-22 03:16:48.394558'),(93,'shoppingcart','0003_auto_20161205_1514','2018-08-22 03:16:51.452036'),(94,'ga_shoppingcart','0001_initial','2018-08-22 03:16:52.162494'),(95,'ga_shoppingcart','0002_certificateitemadditionalinfo','2018-08-22 03:16:52.853827'),(96,'ga_shoppingcart','0003_auto_20161205_1514','2018-08-22 03:16:56.589334'),(97,'ga_survey','0001_initial','2018-08-22 03:16:57.375301'),(98,'ga_task','0001_initial','2018-08-22 03:16:58.202989'),(99,'gx_org_group','0001_initial','2018-08-22 03:17:03.275026'),(100,'gx_member','0001_initial','2018-08-22 03:17:06.356925'),(101,'gx_member','0002_auto_20180621_1207','2018-08-22 03:17:27.292699'),(102,'gx_member','0003_auto_20180713_1147','2018-08-22 03:17:28.220620'),(103,'gx_member','0004_auto_20180719_1104','2018-08-22 03:17:29.171039'),(104,'lms_xblock','0001_initial','2018-08-22 03:17:30.146311'),(105,'milestones','0001_initial','2018-08-22 03:17:33.218295'),(106,'milestones','0002_data__seed_relationship_types','2018-08-22 03:17:33.286538'),(107,'mobile_api','0001_initial','2018-08-22 03:17:34.066049'),(108,'notes','0001_initial','2018-08-22 03:17:34.886532'),(109,'oauth2','0001_initial','2018-08-22 03:17:39.253653'),(110,'oauth2_provider','0001_initial','2018-08-22 03:17:40.169934'),(111,'oauth_provider','0001_initial','2018-08-22 03:17:42.315724'),(112,'organizations','0001_initial','2018-08-22 03:17:42.615473'),(113,'programs','0001_initial','2018-08-22 03:17:43.593483'),(114,'programs','0002_programsapiconfig_cache_ttl','2018-08-22 03:17:44.544295'),(115,'programs','0003_auto_20151120_1613','2018-08-22 03:17:48.415131'),(116,'self_paced','0001_initial','2018-08-22 03:17:49.405511'),(117,'sessions','0001_initial','2018-08-22 03:17:49.497307'),(118,'sites','0001_initial','2018-08-22 03:17:49.580746'),(119,'splash','0001_initial','2018-08-22 03:17:50.603531'),(120,'status','0001_initial','2018-08-22 03:17:53.986080'),(121,'student','0002_auto_20151208_1034','2018-08-22 03:17:55.721143'),(122,'student','0003_auto_20170530_1844','2018-08-22 03:17:57.660482'),(123,'submissions','0001_initial','2018-08-22 03:17:58.690990'),(124,'submissions','0002_auto_20151119_0913','2018-08-22 03:17:58.939311'),(125,'survey','0001_initial','2018-08-22 03:18:00.306571'),(126,'teams','0001_initial','2018-08-22 03:18:03.939027'),(127,'third_party_auth','0001_initial','2018-08-22 03:18:09.558206'),(128,'track','0001_initial','2018-08-22 03:18:09.642091'),(129,'user_api','0001_initial','2018-08-22 03:18:17.568474'),(130,'util','0001_initial','2018-08-22 03:18:18.662367'),(131,'util','0002_data__default_rate_limit_config','2018-08-22 03:18:18.726509'),(132,'verify_student','0001_initial','2018-08-22 03:18:31.539577'),(133,'verify_student','0002_auto_20151124_1024','2018-08-22 03:18:32.937929'),(134,'verify_student','0003_auto_20151113_1443','2018-08-22 03:18:35.826164'),(135,'wiki','0001_initial','2018-08-22 03:19:09.952036'),(136,'wiki','0002_remove_article_subscription','2018-08-22 03:19:10.026563'),(137,'workflow','0001_initial','2018-08-22 03:19:10.424494'),(138,'xblock_django','0001_initial','2018-08-22 03:19:11.773696'),(139,'contentstore','0001_initial','2018-08-22 03:19:39.429123'),(140,'course_creators','0001_initial','2018-08-22 03:19:39.523929'),(141,'ga_maintenance_cms','0001_initial','2018-08-22 03:19:39.573726'),(142,'xblock_config','0001_initial','2018-08-22 03:19:39.960842');
/*!40000 ALTER TABLE `django_migrations` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2018-08-22 12:19:44
