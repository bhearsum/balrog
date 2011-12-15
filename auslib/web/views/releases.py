import simplejson as json

from sqlalchemy.exc import SQLAlchemyError

from flask import request, Response, jsonify
from flask.views import MethodView

from buildtools.retry import retry

from auslib.blob import ReleaseBlobV1, CURRENT_SCHEMA_VERSION
from auslib.web.base import app, db
from auslib.web.views.base import requirelogin, requirepermission

import logging
log = logging.getLogger(__name__)

class SingleLocaleView(MethodView):
    """/releases/[release]/builds/[platform]/[locale]"""
    def get(self, release, platform, locale):
        locale = db.releases.getLocale(release, platform, locale)
        return jsonify(locale)

    @requirelogin
    @requirepermission()
    def put(self, release, platform, locale, changed_by):
        new = True
        try:
            # Collect all of the release names that we should put the data into
            product = request.form['product']
            version = request.form['version']
            localeBlob = json.loads(request.form['details'])
            copyTo = json.loads(request.form.get('copyTo', '[]'))
        except (KeyError, json.JSONDecodeError), e:
            return Response(status=400, response=e.args)

        for rel in [release] + copyTo:
            releaseObj = db.releases.getReleases(name=rel)[0]
            # If the release already exists, do some verification on it, and possibly update
            # the version.
            if releaseObj:
                # If the product name provided in the request doesn't match the one we already have
                # for it, fail. Product name changes shouldn't happen here, and any client trying to
                # is probably broken.
                if product != releaseObj['product']:
                    return Response(status=400, response="Product name '%s' doesn't match the one on the release object ('%s') for release '%s'" % (product, releaseObj['product'], rel))

                # However, we _should_ update the version because some rows (specifically,
                # the ones that nightly update rules point at) have their version change over time.
                if version != releaseObj['version']:
                    def updateVersion():
                        old_data_version = db.releases.getReleases(name=rel)[0]['data_version']
                        db.releases.updateRelease(name=rel, version=version, changed_by=changed_by, old_data_version=old_data_version)
                    retry(updateVersion, sleeptime=5, retry_exceptions=(SQLAlchemyError,))
                # If it does exist, and this is this is the first release (aka, the one in the URL),
                # see if the locale exists, for purposes of setting the correct Response code.
                if rel == release:
                    try:
                        db.releases.getLocale(rel, platform, locale)
                        new = False
                    except:
                        pass
            # If the release doesn't exist, create it.
            else:
                releaseBlob = ReleaseBlobV1(name=rel, schema_version=CURRENT_SCHEMA_VERSION)
                retry(db.releases.addRelease, sleeptime=5, retry_exceptions=(SQLAlchemyError,),
                      kwargs=dict(name=rel, product=product, version=version, blob=releaseBlob, changed_by=changed_by))
            # We need to wrap this in order to make it retry-able.
            def updateLocale():
                old_data_version = db.releases.getReleases(name=rel)[0]['data_version']
                db.releases.addLocaleToRelease(rel, platform, locale, localeBlob, old_data_version, changed_by)
            retry(updateLocale, sleeptime=5, retry_exceptions=(SQLAlchemyError,))
        if new:
            return Response(status=201)
        else:
            return Response(status=200)

app.add_url_rule('/releases/<release>/builds/<platform>/<locale>', view_func=SingleLocaleView.as_view('single_locale'))
