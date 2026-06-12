import random
import string
import os

INPUT_FILE = os.path.abspath("domains.txt")
OUTPUT_FILE = os.path.abspath("subdomains.txt")
SUBDOMAINS_PER_DOMAIN = 1000


def random_subdomain(length=6):
    """Generate a random lowercase subdomain string."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def generate_subdomains(domain, count):
    """Generate unique subdomains for a domain."""
    subs = set()
    while len(subs) < count:
        subs.add(f"http://{random_subdomain()}.{domain}")  # <-- added http://
    return subs


def main():
    all_subdomains = []

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        domains = [line.strip() for line in f if line.strip()]

    for domain in domains:
        all_subdomains.extend(generate_subdomains(domain, SUBDOMAINS_PER_DOMAIN))

    # 🔥 shuffle all results randomly
    random.shuffle(all_subdomains)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for sub in all_subdomains:
            f.write(sub + "\n")

    print(f"Generated {len(all_subdomains)} subdomains and saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
