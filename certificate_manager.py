import os
import subprocess
import logging
import schedule
import time
from datetime import datetime, timedelta
from typing import List, Dict
import CloudFlare
from dotenv import load_dotenv
from pythonjsonlogger import jsonlogger

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger()
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

class CertificateManager:
    def __init__(self):
        self.cf = CloudFlare.CloudFlare(token=os.getenv('CLOUDFLARE_API_TOKEN'))
        self.domains = os.getenv('DOMAINS', '').split(',')
        self.email = os.getenv('CERTBOT_EMAIL')
        self.staging = os.getenv('CERTBOT_STAGING', 'false').lower() == 'true'
        self.renewal_interval = int(os.getenv('RENEWAL_INTERVAL_DAYS', 30))
        self.check_interval = int(os.getenv('RENEWAL_CHECK_INTERVAL_HOURS', 12))

    def setup_cloudflare_dns(self, domain: str, token: str) -> None:
        """Set up DNS validation for Cloudflare."""
        try:
            # Create DNS record for ACME challenge
            zone_name = domain.split('.')[-2] + '.' + domain.split('.')[-1]
            zone = self.cf.zones.get(params={'name': zone_name})[0]
            
            dns_record = {
                'name': f'_acme-challenge.{domain}',
                'type': 'TXT',
                'content': token,
                'ttl': 120
            }
            
            self.cf.zones.dns_records.post(zone['id'], data=dns_record)
            logger.info(f"Created DNS record for {domain}", extra={'domain': domain})
        except Exception as e:
            logger.error(f"Failed to create DNS record for {domain}", 
                        extra={'domain': domain, 'error': str(e)})
            raise

    def cleanup_cloudflare_dns(self, domain: str) -> None:
        """Clean up DNS validation records."""
        try:
            zone_name = domain.split('.')[-2] + '.' + domain.split('.')[-1]
            zone = self.cf.zones.get(params={'name': zone_name})[0]
            
            records = self.cf.zones.dns_records.get(zone['id'], 
                params={'name': f'_acme-challenge.{domain}', 'type': 'TXT'})
            
            for record in records:
                self.cf.zones.dns_records.delete(zone['id'], record['id'])
            
            logger.info(f"Cleaned up DNS records for {domain}", extra={'domain': domain})
        except Exception as e:
            logger.error(f"Failed to cleanup DNS records for {domain}", 
                        extra={'domain': domain, 'error': str(e)})

    def obtain_certificate(self, domain: str) -> None:
        """Obtain a new certificate for the domain."""
        try:
            cmd = [
                'certbot', 'certonly',
                '--dns-cloudflare',
                '--dns-cloudflare-credentials', '/root/.secrets/cloudflare.ini',
                '--email', self.email,
                '--agree-tos',
                '--non-interactive'
            ]

            if self.staging:
                cmd.append('--staging')

            if '*' in domain:
                cmd.extend(['--server', 'https://acme-v02.api.letsencrypt.org/directory'])
                cmd.extend(['--dns-cloudflare-propagation-seconds', '60'])
                cmd.extend(['-d', domain])
            else:
                cmd.extend(['-d', domain])

            logger.info(f"Attempting to obtain certificate for {domain}", 
                       extra={'domain': domain})
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Successfully obtained certificate for {domain}", 
                           extra={'domain': domain})
            else:
                logger.error(f"Failed to obtain certificate for {domain}", 
                           extra={'domain': domain, 'error': result.stderr})
                raise Exception(f"Certificate acquisition failed: {result.stderr}")

        except Exception as e:
            logger.error(f"Error obtaining certificate for {domain}", 
                        extra={'domain': domain, 'error': str(e)})
            raise

    def check_certificates(self) -> None:
        """Check and renew certificates if needed."""
        for domain in self.domains:
            try:
                # Check certificate expiration
                cmd = ['certbot', 'certificates', '--domain', domain]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    # Parse expiration date and check if renewal is needed
                    # This is a simplified check - you might want to add more robust parsing
                    if 'VALID: ' in result.stdout:
                        expiration_str = result.stdout.split('VALID: ')[1].split('\n')[0]
                        expiration_date = datetime.strptime(expiration_str, '%Y-%m-%d')
                        
                        if (expiration_date - datetime.now()).days <= self.renewal_interval:
                            logger.info(f"Certificate for {domain} needs renewal", 
                                      extra={'domain': domain})
                            self.obtain_certificate(domain)
                else:
                    logger.warning(f"No certificate found for {domain}, obtaining new one", 
                                 extra={'domain': domain})
                    self.obtain_certificate(domain)

            except Exception as e:
                logger.error(f"Error checking certificate for {domain}", 
                           extra={'domain': domain, 'error': str(e)})

    def run(self) -> None:
        """Run the certificate manager service."""
        logger.info("Starting certificate manager service")
        
        # Schedule certificate checks
        schedule.every(self.check_interval).hours.do(self.check_certificates)
        
        # Run initial check
        self.check_certificates()
        
        # Keep the service running
        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == "__main__":
    manager = CertificateManager()
    manager.run() 