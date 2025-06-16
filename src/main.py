from routing import install_all_routes

APP_ID = "org.onosproject.cli"  # or your own registered app name

def main():
    print("Installing routing intents for all host pairs...")
    install_all_routes(APP_ID)
    print("Done.")

if __name__ == "__main__":
    main()

