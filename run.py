import truststore

truststore.inject_into_ssl()

from naverblogbot.app import main

main()
