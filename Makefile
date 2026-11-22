# Traduções (gettext)
#
#   make            compila os .po em usr/share/locale/<idioma>/LC_MESSAGES/*.mo
#   make pot        extrai os textos do código para po/msensor-tester.pot
#   make update-po  atualiza os .po com os textos novos/alterados do código
#   make stats      mostra quantos textos estão traduzidos em cada idioma
#   make clean      apaga os .mo compilados
#
# Para adicionar um idioma: msginit -i po/msensor-tester.pot -l <código> -o po/<código>.po
# e acrescente o código em po/LINGUAS.

DOMAIN    := msensor-tester
APPDIR    := usr/share/msensor-tester
LOCALEDIR := usr/share/locale
PODIR     := po
POT       := $(PODIR)/$(DOMAIN).pot
VERSION   := $(shell sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' $(APPDIR)/core/__init__.py)
LINGUAS   := $(shell grep -v '^\#' $(PODIR)/LINGUAS)
SOURCES   := $(shell find $(APPDIR) -name '*.py' ! -path '*/__pycache__/*' | LC_ALL=C sort)
MO_FILES  := $(foreach lang,$(LINGUAS),$(LOCALEDIR)/$(lang)/LC_MESSAGES/$(DOMAIN).mo)

.PHONY: all mo pot update-po stats clean

all: mo

mo: $(MO_FILES)

$(LOCALEDIR)/%/LC_MESSAGES/$(DOMAIN).mo: $(PODIR)/%.po
	@mkdir -p $(dir $@)
	msgfmt --check --output-file=$@ $<

pot:
	xgettext --language=Python --from-code=UTF-8 --keyword=_ \
		--add-comments=TRANSLATORS: \
		--package-name=$(DOMAIN) --package-version=$(VERSION) \
		--msgid-bugs-address=https://github.com/narayanls/msensor-tester/issues \
		--output=$(POT) $(SOURCES)

update-po: pot
	@for lang in $(LINGUAS); do \
		echo "msgmerge $(PODIR)/$$lang.po"; \
		msgmerge --update --backup=none --quiet $(PODIR)/$$lang.po $(POT); \
	done

stats:
	@for lang in $(LINGUAS); do \
		printf '%s: ' $$lang; msgfmt --statistics --output-file=/dev/null $(PODIR)/$$lang.po; \
	done

clean:
	rm -f $(MO_FILES)
