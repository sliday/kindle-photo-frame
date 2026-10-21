# Google Photos on the Kindle frame, privately

Research date: 2026-10-20. Research only: I installed nothing, created no accounts or cloud projects, and changed no settings.

**Setup:** a jailbroken Kindle Paperwhite 4 (1072 x 1448) running a Go photo-frame binary over Wi-Fi, with no browser on the device. The owner's photos sit in a private Google Photos library, and the owner refuses "anyone with the link" sharing. The frame's local photo set stays as the fallback.

**Main question (refined by the owner):** can the owner keep one private album, add photos to it from the phone, and have the Kindle pick up the new ones automatically, with no per-photo action and no link sharing?

Quotes come from official Google pages first (developers.google.com, support.google.com, blog.google), then secondary sources. Items marked **UNVERIFIED** are things I could not confirm from a primary source.

---

## 0. Answer to the main question

**No official Google route gives an individual's own device an ever-updating private album.** Google built that capability, the Ambient API, and limits it to accepted partners. Every route open to an individual falls into one of three groups:

- it reads only photos your own app uploaded (Library API),
- it reads only photos you pick by hand in each session (Picker API), or
- it moves the album out of Google Photos (a Drive folder, Immich, or a synced folder).

| Rank | Route | Delivers "add on phone, frame updates by itself"? | Open to an individual? | Official? |
|---|---|---|---|---|
| 1 | Ambient API (album as "media source") | Yes, exactly this | No, partner program only | Yes |
| 2 | Browser automation of your own logged-in Google Photos session, run on a home server | Yes (latency = how often you poll) | Yes | No, ToS grey area |
| 3 | Google's own Nest Hub / Google TV photo frame | Yes | Yes | Yes, but not on a Kindle |
| 4 | Private Drive folder shared with a second "frame" account; Kindle reads it with `drive.readonly` | Yes, but the phone action becomes "Share to Drive folder" instead of "Add to album" | Yes (personal, unverified app) | Yes |
| 5 | Self-hosted Immich album (or a Syncthing folder) | Yes, but the album lives outside Google Photos | Yes | Yes (no Google) |
| 6 | Picker API (QR code on the Kindle) | No. You re-pick new photos each time | Yes (personal, unverified app) | Yes |
| 7 | Library API app-created album | No. It ignores photos you add in the Photos app | Yes | Yes |
| 8 | Album shared privately with a second account | No. Google removed the shared-album API | n/a | n/a |
| 9 | Takeout scheduled export | No. It runs every 2 months for 1 year | Yes | Yes |
| 10 | rclone, gphotos-sync | No. rclone reads only its own uploads; gphotos-sync is archived | Yes | Yes |

My recommendation is in section 9.

---

## 1. Library API after the 2025 change

### Dates

- Google posted the announcement in September 2024. The release notes add "September 16, 2024: Introduced the new Picker API" and "This release we announced key changes to the Library API (effective March 31, 2025)." ([release notes](https://developers.google.com/photos/support/release-notes))
- The cutoff: "These changes will take effect March 31, 2025." ([updates](https://developers.google.com/photos/support/updates))
- The rollout: "April 1, 2025. This release implements the previously announced changes to the Photos APIs. Removal of some scopes from the Library API. Restriction of several methods to only work with app created content." ([release notes](https://developers.google.com/photos/support/release-notes))
- **Secondary:** MagicMirror users saw their tokens stop working at different times through May 2025. The maintainer wrote, "I think it is depended on the rollout progress from Google side." ([MMM-GooglePhotos #194](https://github.com/hermanho/MMM-GooglePhotos/issues/194))

### Scopes removed and scopes that remain

> "the following scopes will be removed from the Library API after March 31, 2025: photoslibrary.readonly, photoslibrary.sharing, photoslibrary. The following scopes will remain: photoslibrary.appendonly, photoslibrary.readonly.appcreateddata, photoslibrary.edit.appcreateddata"
> ([updates](https://developers.google.com/photos/support/updates))

> "API calls relying only on these scopes will return a 403 PERMISSION_DENIED after March 31, 2025."
> (same page)

> "Listing, searching, and retrieving media items and albums. What's changing: You can now only list, search, and retrieve albums and media items that were created by your app."
> (same page)

The [authorization page](https://developers.google.com/photos/library/guides/authorization) describes the remaining scopes:

- `photoslibrary.appendonly`: "Write access only. Access to upload bytes, create media items, create albums, and add enrichments. Only allows new media to be created in the user's library and in albums created by the app."
- `photoslibrary.readonly.appcreateddata`: "Read access to media items and albums created by the developer. ... Intended to be requested together with the photoslibrary.appendonly scope."
- `photoslibrary.edit.appcreateddata`: "Edit access only. Access to change these details for albums and media items created by the developer."

### (a) Can the app read photos you add to its album from the Google Photos app? No.

Google never addresses this exact case in one sentence. Four official statements, read together, rule it out:

1. The `mediaItems.search` reference: "Searches for app created media items in a user's Google Photos library. Only media items and ablums created by your app are returned. ... If an app created album is set, all media items in the specified album are returned." ([mediaItems.search](https://developers.google.com/photos/library/reference/rest/v1/mediaItems/search)) The "ablums" typo is Google's.
2. The same page, on the `excludeNonAppCreatedData` filter: "If set, the results exclude media items that were not created by this app. Defaults to false (all media items are returned). This field is ignored if the photoslibrary.readonly.appcreateddata scope is used." The filter is ignored because that scope already excludes media the app did not create.
3. The legacy list guide: "The photoslibrary.readonly.appcreateddata scope allows access only to media items that were created by the app." ([legacy list guide](https://developers.google.com/photos/library/legacy/guides/list))
4. The current albums guide: "You can add media items created by your app to albums created by your app by calling albums.batchAddMediaItems." ([manage albums](https://developers.google.com/photos/library/guides/manage-albums))

Real-world reports:

- **Search-engine summary only:** a blog post by Kilian Lehn reports a test album that showed `mediaItemsCount: 12` after manual adds, with the API marked "Blocked (returns 0 items)". The site returned HTTP 521 on two tries and the Wayback Machine rate-limited me, so I could not read the page myself. **UNVERIFIED** quote. ([familylehn.com](https://familylehn.com/google-photos-api-open-letter))
- A MagicMirror user who switched to `readonly.appcreateddata` got this reply: "That is not true. It only allows you to download data that your app uploaded. We want to access all media. This is not possible anymore." Another user wrote: "So anything you've added to albums using your personal account doesn't work." ([MMM-GooglePhotos #194](https://github.com/hermanho/MMM-GooglePhotos/issues/194))

**Conclusion:** the "app-created album" trick fails. The frame would see only photos its own client uploaded through the API.

### Two more constraints

- "Resources created through any of the Google Photos APIs can only be accessed or modified using the original client ID used to create them." ([configure your app](https://developers.google.com/photos/overview/configure-your-app))
- "Caution: Don't cache user photos and videos. Instead, store the media item id and request its details again when you need them. ... direct access through the baseUrl expires after 60 minutes." ([Library list guide](https://developers.google.com/photos/library/guides/list))

---

## 2. (b) Sharing the album with a second Google account

Google Photos supports private sharing with specific people:

> "To make a shared album private, remove all collaborators and turn off link sharing."

> "You can control which Google Account users have access to your album."

> "If you remove someone from a shared album, but have link sharing turned on, anyone with the original link can still view the album."

([shared album controls](https://support.google.com/photos/answer/9789702)). So the owner could share the album with a "frame" account and turn link sharing off.

**No API can read that shared album any more.**

> "Shared albums and the associated API functions (share, unshare, get, join, leave, and list) will return a 403 PERMISSION_DENIED after March 31, 2025."

The methods table lists `albums.share`, `albums.unshare`, `sharedAlbums.get`, `sharedAlbums.join`, `sharedAlbums.leave` and `sharedAlbums.list` with "Scopes remaining: None. Scopes removed: photoslibrary.sharing." ([updates](https://developers.google.com/photos/support/updates))

The second account's `readonly.appcreateddata` token sees nothing, because its app created none of those photos. Partner sharing ([help](https://support.google.com/photos/answer/7378858)) has no API either.

The Ambient API reference describes media sources only as "albums or photo collections the user selects". I found nothing saying whether shared albums count. **UNVERIFIED**, and moot without partner access.

---

## 3. Picker API

### Scope and classification

- Scope: `https://www.googleapis.com/auth/photospicker.mediaitems.readonly`, "Access to create, get, and delete sessions, and to list media items for sessions." ([authorization](https://developers.google.com/photos/library/guides/authorization))
- Classification: Google's Photos pages never say "sensitive" or "restricted". The authorization page says: "If your application accesses the Google Photos APIs, it must pass the OAuth verification review. If you see unverified app on the screen when testing your application, you must submit a verification request to remove it."
- The unverified-app screen applies only to "an app ... that requests a sensitive or restricted OAuth scope" ([unverified apps](https://support.google.com/cloud/answer/7454865)), so the Picker scope is at least sensitive.
- A developer PR states: "The scope is `photospicker.mediaitems.readonly`, which Google counts as sensitive." ([LaugeM/stikling #125](https://github.com/LaugeM/stikling/pull/125)) Sensitive rather than restricted: **UNVERIFIED** from a primary source. Checking the lock icon on the Cloud Console Data Access page would settle it.
- Google's OAuth scope catalogue lists no Picker or Ambient scope at all ([scopes](https://developers.google.com/identity/protocols/oauth2/scopes)).

### Client types

- Google's setup example uses a web client: "In this example, the application type is Web application." Google adds: "Plan carefully and choose the correct client ID type for the Photos API you are using." ([configure your app](https://developers.google.com/photos/overview/configure-your-app))
- Google's docs name no client-type restriction for the Picker.
- **Secondary evidence for a Desktop (installed) client:** an embedded photo-frame project documents "Credentials -> Create credentials -> OAuth client ID -> **Desktop app**", a login with "PKCE and a loopback redirect (`http://127.0.0.1:<port>/`)", and a refresh token "copied to the device". ([PyDevices gphotos_auth.py](https://github.com/PyDevices/pydevices-examples/blob/HEAD/tools/gphotos_auth.py)) That matches the Kindle's needs. Web clients work in other projects ([obsidian-google-photos](https://github.com/alangrainger/obsidian-google-photos/blob/HEAD/docs/Setup-PickerAPI.md), [gphotos-integration](https://github.com/moimart/gphotos-integration)).
- Android and iOS client types: no Picker-specific statement found. **UNVERIFIED.**
- TV / limited-input (device flow): not usable, because the device flow "is supported only for" email, openid, profile, `drive.appdata`, `drive.file`, `youtube` and `youtube.readonly` ([limited-input devices](https://developers.google.com/identity/protocols/oauth2/limited-input-device)).

### Session lifecycle

Quotes from [sessions guide](https://developers.google.com/photos/picker/guides/sessions), [get started](https://developers.google.com/photos/picker/guides/get-started-picker) and [sessions reference](https://developers.google.com/photos/picker/reference/rest/v1/sessions).

1. **Create:** "sessions.create generates a new session, returning a unique pickerUri that you can present to your users. The session remains active until either the user has successfully selected media items, or the session times out."
2. **Show:** "Provide the pickerUri to your users (either as a clickable link or a QR code)." Also: "To view this page successfully, the user must be logged into the Google account that owns this session in their web browser." And: "The pickerUri cannot be opened in an iframe due to security reasons."
3. **Poll:** "periodically poll the sessions.get endpoint ... The mediaItemsSet property in the response returns true when the user has completed their selection." The `pollingConfig` fields are `pollInterval` ("Recommended time between poll requests") and `timeoutIn` ("The length of time after which the client should stop polling. A value of 0 indicates that the client should stop polling"). `pollingConfig` "is only populated if media items have not yet been picked".
4. **List:** "Make a GET request to https://photospicker.googleapis.com/v1/mediaItems, providing the sessionId as a query parameter", following `nextPageToken` ([media items guide](https://developers.google.com/photos/picker/guides/media-items)). A picked item's `id` "is a persistent identifier that can be used between sessions to identify this media item" ([mediaItems reference](https://developers.google.com/photos/picker/reference/rest/v1/mediaItems)). The frame can use it to skip duplicates.
5. **Delete:** "It's a best practice to delete sessions once the user has selected media items and your app has retrieved the media item bytes."
6. **Expiry:** `expireTime` is the "Time when access to this session (and its picked media items) will expire." Google publishes no fixed length. Two reports disagree:
   - "one created 2026-09-23 carried `expireTime` 2026-09-30, about seven days" ([PyDevices #145](https://github.com/PyDevices/pydevices-examples/issues/145))
   - "Picker sessions last roughly 24 hours" ([gphotos-integration README](https://github.com/moimart/gphotos-integration))

   **UNVERIFIED.** Download the bytes right after the pick and do not rely on the session afterwards.
7. **Done:** "Once a user taps the Done button to complete a picking session, the pickerUri will no longer work. Create a new session to allow the user to pick more photos." ([sessions.create](https://developers.google.com/photos/picker/reference/rest/v1/sessions/create))

### QR code on a separate device: documented

> "This behavior is only recommended for web flows, and not for experiences where users might scan a QR code to open Google Photos on a different device."

> "Display the pickerUri as both a QR code and a URL."

> "For devices with limited input capabilities (e.g., kiosks, tablets, smart TVs), check your hardware manufacture's recommendations on text size and QR code width."

([picking experience](https://developers.google.com/photos/picker/guides/picking-experience))

Google's January 2025 email to developers, forwarded in [MMM-GooglePhotos #208](https://github.com/hermanho/MMM-GooglePhotos/issues/208), says: "You can also use this API to allow users to pick photos to display on photo frames." This is secondary: a user pasted the email.

### Albums: you cannot pick a whole album

> "This page will always display the most recent photos from your user's Google Photos library. Albums, favorites, and other common photos categories are not show directly. Users can search for photos using various criteria, such as keywords, dates, locations, and album titles."

Google's suggested prompt: "Connect to Google Photos, then search for the album you want to share." ([picking experience](https://developers.google.com/photos/picker/guides/picking-experience))

You get a one-time copy of the items you select. Photos added to the album later do not appear. Whether the picker offers "select all" on a search result is **UNVERIFIED**.

### Max items

> "maxItemCount ... Defaults to 2000 if not specified. If unspecified or set to 0, at most 2000 items can be picked. Values above 2000 will be coerced to 2000."

([sessions reference](https://developers.google.com/photos/picker/reference/rest/v1/sessions))

### baseUrl lifetime and authentication

> "Base URLs remain active for 60 minutes, but can expire sooner if the user revokes your app's permissions through their Google Account settings."

> "Requests to a PickedMediaItem.mediaFile baseUrl must include an Authorization header with a valid OAuth 2.0 bearer token."

([media items guide](https://developers.google.com/photos/picker/guides/media-items))

### URL size parameters (same page)

- "If you use the base URL you must specify a download parameter, or both the maximum width and the maximum height."
- `=wW-hH`, for example `=w2048-h1024`. Add `-c` to crop to the exact size. "The size (in pixels) should be in the range [1, 16383]."
- `=d`: "download the image retaining all the Exif metadata except the location metadata."
- `=dv`: the video bytes, "a high quality, transcoded version of the original video", not compatible with `w`/`h`.
- `-no`: a video thumbnail without the play button.
- For the Paperwhite 4, `=w1072-h1448` keeps the aspect ratio. Use `=w1448-h1448` if the frame rotates landscape shots.

### Quotas

> "The quota limit for requests to the Photos Picker API is 100,000 requests per minute per project. The quota limit for requests to access media bytes (by loading a photo or video from a base URL) is 1,000,000 requests per minute per project."

Library API: "10,000 requests per project per day", and 75,000 per day for bytes. ([limits and quotas](https://developers.google.com/photos/overview/api-limits-quotas))

> "If the client application creates too many sessions per user, a RESOURCE_EXHAUSTED error is returned. Clients are unlikely to reach these limits under normal circumstances."

([sessions.create](https://developers.google.com/photos/picker/reference/rest/v1/sessions/create))

### Policy notes

> "use cases where the user needs to grant access for a limited set of content for a limited time period; for example, printing, editing, and social use cases, must use the Photos Picker API."

> "Do not make a substitute for Google Photos. For example, do not use the APIs to create a general purpose photo gallery app."

([Photos API User Data and Developer Policy](https://developers.google.com/photos/support/api-policy))

A single-user frame showing a copy of picked photos fits the intent. The partner form lists "Allow users to pick media items from their library to share a copy with your app" as one use. The "don't cache" warning appears in the Library guide, not in the Picker guides.

---

## 4. OAuth consent screen and token lifetime

### Testing mode: 7-day refresh tokens

> "A Google Cloud Platform project with an OAuth consent screen configured for an external user type and a publishing status of "Testing" is issued a refresh token expiring in 7 days, unless the only OAuth scopes requested are a subset of name, email address, and user profile (through the userinfo.email, userinfo.profile, openid scopes, or their OpenID Connect equivalents)."

([OAuth 2.0 overview](https://developers.google.com/identity/protocols/oauth2#expiration))

### Production, unverified, personal use

> "Personal use. One use case is if you are the only user of your app or if your app is used by only a few users, all of whom are known personally to you. You and your limited number of users might be comfortable with advancing through the unverified app screen and granting your personal accounts access to your app. Note: A user cap restricts the number of Google Accounts able to grant access to your unverified app."

This text is identical on the [sensitive scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification) and [restricted scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification) pages.

For Testing-mode projects, the same pages add: "Your app is still subject to a tester warning screen, ... a user cap is in effect, and the refresh token lifetime is limited."

The user cap:

> "New user cap. Apps that present the unverified app screen to users. 100 new users in total, after the app presents the unverified app screen."

([unverified apps](https://support.google.com/cloud/answer/7454865))

**Secondary (rclone docs):** publishing an unverified personal app works, and avoids the weekly expiry.

> "Keeping the application in "Testing" will work as well, but the limitation is that any grants will expire after a week ... So for typical personal rclone use you can leave the app unverified, accept the warning screen, and publish it."

rclone also notes: "If the "PUBLISH APP" button is greyed out, Google now requires a homepage URL and a privacy policy URL before publishing, even for a personal single-user app." ([rclone Drive docs](https://rclone.org/drive/)) That last requirement is **UNVERIFIED** from Google.

### Verification and security assessment

- The Photos docs require verification for a public launch: "Before you can launch a public application that accesses the Photos APIs, your app must be reviewed by Google." ([configure your app](https://developers.google.com/photos/overview/configure-your-app))
- The personal-use exception covers a one-owner frame.
- A security assessment (CASA) applies only to restricted scopes on apps going through verification that touch servers: "Every app that requests access to Google users' restricted data and has the ability to access data from or through a third-party server must go through a security assessment." ([restricted scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification))
- A personal, unverified frame avoids both, but keeps the warning screen and the 100-user cap.

### Refresh token lifetime in production (Desktop or any client)

Google sets no fixed expiry. A refresh token stops working when:

> "The user has revoked your app's access. The refresh token has not been used for six months. The user changed passwords and the refresh token contains Gmail scopes. The user account has exceeded a maximum number of granted (live) refresh tokens. The user granted time-based access to your app and the access expired."

> "There is currently a limit of 100 refresh tokens per Google Account per OAuth 2.0 client ID. If the limit is reached, creating a new refresh token automatically invalidates the oldest refresh token without warning."

([OAuth 2.0 overview](https://developers.google.com/identity/protocols/oauth2#expiration))

A frame that refreshes daily keeps its token until someone revokes it.

### Getting the token onto the Kindle

The Desktop flow needs a browser on the same machine as the redirect listener: "desktop apps must open the system browser and supply a local redirect URI (such as a loopback IP address)". The copy-paste flow is gone: "The redirect_uri parameter may refer to the OAuth out-of-band (OOB) flow that has been deprecated and is no longer supported." ([installed apps](https://developers.google.com/identity/protocols/oauth2/native-app))

The practical pattern: run the consent once on a laptop with a small helper, then copy the client ID, client secret and refresh token to the Kindle. The PyDevices project above does this.

---

## 5. (c) Ambient API (photo frames and TVs)

### What it is

> "The Ambient API lets you create immersive slideshow experiences on ambient devices. Enable users to view their photos and videos on devices like smart TVs and photo frames, with curated slideshows that use Google Photos' intelligence."

([partner program](https://developers.google.com/photos/partner-program/overview#ambient-api))

### Partner-only

> "To get access to the Ambient API, you must first be accepted into the partner program."

(same page)

### What partners get: live albums

- The flow uses the TV / limited-input OAuth flow with scope `photosambient.mediaitems`. The app creates a device, shows a `settingsUri` QR code, and the user "can configure the media sources (e.g., albums) they want to display on their ambient device." ([Ambient get started](https://developers.google.com/photos/ambient/guides/get-started), [configure](https://developers.google.com/photos/ambient/guides/configure-your-app))
- On media sources: "Media sources are albums or photo collections the user selects to display on a device." ([devices reference](https://developers.google.com/photos/ambient/reference/rest/v1/devices))
- On listing: "Returns a list of ambient media items from user-configured media sources for the specified device. By default, listMediaItems provides the Ambient experience, returning a curated set of media items from all user-configured sources. Optionally, you can include mediaSourceId in the request to retrieve a paginated list of items from a specific media source." Also: "Client applications are limited to 240 requests per device per day." Up to 100 items per page. ([mediaItems.list](https://developers.google.com/photos/ambient/reference/rest/v1/mediaItems/list))
- Google's UX rule asks for freshness: "regularly poll for updates to the media items list ... to verify the displayed content reflects the user's current selections." The guidelines carry a "Beta" label. ([Ambient UX guidelines](https://developers.google.com/photos/support/ambient-ux-guidelines))
- Google filters content: it excludes "Functional images (e.g., screenshots, documents, receipts)", low-quality images, and "Content identified as highly personal or sensitive". ([Ambient media items](https://developers.google.com/photos/ambient/guides/media-items))
- `photosambient.mediaitems` is absent from the public device-flow scope list in section 3. Google presumably allowlists it per partner. That is an inference: **UNVERIFIED.**

### Can an individual get access?

- The interest form ([services.google.com/fb/forms/photospartnerprogram](https://services.google.com/fb/forms/photospartnerprogram/)) asks for "Company Name", "Company URL", employee count and "How many eligible devices or app installs do you anticipate" (smallest bucket: "Less than 100,000").
- One checkbox reads "Access to user photos for photo frames or screensavers".
- Nothing bars an individual from applying. Whether Google accepts one is **UNVERIFIED**, and the form's shape points to no.

### Current status

- **Secondary:** Aura shipped Ambient-based sync in June 2026. 9to5Google (2026-06-04) quotes Aura: "Sync entire Google Photos albums with the frame via the Aura app's "Auto-Add" function ... any additional photos you add to these albums on Google Photos will be automatically sent to the Aura frame." ([9to5Google](https://9to5google.com/2026/06/04/google-photos-support-has-returned-for-auras-digital-photo-frames/))
- An rclone forum thread (June-July 2026) discusses the API, and nobody there reports individual access ([rclone forum](https://forum.rclone.org/t/google-photos-ambient-api/53876)).
- **Secondary, low weight:** devdad.kr (September 2026): "Auto-updating albums are now reserved for Google's own devices and for frame makers Google accepts as partners." ([devdad.kr](https://devdad.kr/blog/google-photos-android-photo-frame.html))

### Google's own devices

Nest displays can show "your private Google Photos albums and your shared albums that have a name" ([Google Home help](https://support.google.com/googlehome/answer/9136992)). That works, but not on a Kindle.

---

## 6. (d) Private Google Drive folder instead of an album

### Scopes

From [Choose Google Drive API scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth):

- `drive.readonly` is **Restricted**: "View and download all your Drive files."
- `drive.file` is **Non-sensitive**: "Create new Drive files, or modify existing files, that you open with an app or that the user shares with an app while using the Google Picker API or the app's file picker."
- "Only specific application types are permitted to use restricted scopes for Google Drive. ... 1. Backup and sync ... 2. Productivity and education ..."
- "If you store restricted scope data on servers (or transmit), then you must go through a security assessment."

Those rules govern verification. The personal-use exception in section 4 covers restricted scopes too.

**Secondary proof that this works in practice:** rclone's setup uses the restricted `drive` scope on a Desktop client, published but unverified, with "a very scary confirmation screen", and keeps working ([rclone Drive docs](https://rclone.org/drive/)).

### Refresh tokens

Same rules as section 4. In production there is no 7-day limit. Tokens die only on revocation, six months without use, or the 100-per-client cap.

### Why not `drive.file`?

Its definition covers files the app created or that the user opened or shared with the app. Photos the owner drops into a folder from the phone fall outside it. Community answers agree, and I found no Google statement on folder children. **UNVERIFIED**; a 10-minute test would settle it.

If it did work, the Kindle could authorize itself with the device flow and a QR code, because `drive.file` is on the device-flow list ([limited-input devices](https://developers.google.com/identity/protocols/oauth2/limited-input-device)).

### Privacy design

A `drive.readonly` token reads the whole Drive of the account that granted it. To contain that:

1. Create a second, empty "frame" Google account.
2. Share one folder with it as Viewer, with general access "Restricted". Drive help: "You can choose if your file should be available to anyone or restricted to only the people with access." ([Drive sharing help](https://support.google.com/drive/answer/2494822))
3. Have the Kindle hold that second account's token.

A stolen Kindle then exposes one folder. One caveat: Drive's sharing table says a viewer can download "Yes, by default. The owner can control it." (same page), so keep downloads enabled for viewers.

That `drive.readonly` lists files shared with the account is standard Drive behavior. I did not test it here: **UNVERIFIED**.

### Getting photos from Google Photos into the folder

- Google stopped the automatic link in 2019: "Starting in July, new photos and videos from Drive won't automatically show in Photos. Similarly, new photos and videos in Photos will not be added to the Photos folder in Drive." ([blog.google](https://blog.google/products-and-platforms/products/photos/simplifying-google-photos-and-google-drive/))
- The remaining "Upload from Drive" option goes the other way only.
- On the phone, the owner selects photos in Google Photos, taps Share, picks the Drive app, and chooses the folder. That is one action per batch, about the same effort as "Add to album". The exact share-sheet labels on Android and iOS, and whether the shared copy is the original quality, are **UNVERIFIED**.
- The Kindle then polls `files.list` for the folder (or the Drive changes feed) every few minutes and downloads new files. Update latency is the poll interval.

---

## 7. (e) Other routes and how frames adapted

### Takeout scheduled exports

> "Automatically create an archive of your selected data every 2 months for one year. The first archive will be created immediately. For Google Photos, you can schedule automatic exports for new and updated data."

- Formats: "Zip files" or "Tgz files".
- Delivery: email link, Drive, Dropbox, OneDrive or Box.
- "Your archive expires in about 7 days."

([Takeout help](https://support.google.com/accounts/answer/3024190))

Update latency is up to two months, so it does not deliver a live album.

### rclone Google Photos backend

> "NB From March 31, 2025 rclone can only download photos it uploaded. This limitation is due to policy changes at Google."

The shared client ID "is being retired and will stop working during 2026", so you need your own. ([rclone Google Photos](https://rclone.org/googlephotos/))

### gphotos-sync

The repo was archived "on Oct 4th 2024" ([repo](https://github.com/gilesknap/gphotos-sync)).

The maintainer quoted Google's reply on the issue tracker: "Our current suggestion is to use Google Takeout to backup your Photos library. We understand the need for an incremental backup solution and are looking into that." ([gphotos-sync #511](https://github.com/gilesknap/gphotos-sync/issues/511), citing [issuetracker 368779600](https://issuetracker.google.com/issues/368779600)). This is secondary; the tracker needs JavaScript and I could not read it.

### MagicMirror MMM-GooglePhotos

The README says: "This plugin is not working currently because new changes in Google Photos API take effect March 2025." The last commit is from 2025-05-07 ([repo](https://github.com/hermanho/MMM-GooglePhotos)).

Users moved to local folders: "I personally went with MMM-ImagesPhotos and a samba share" ([#194](https://github.com/hermanho/MMM-GooglePhotos/issues/194)).

### Picker-based frames

- [moimart/gphotos-integration](https://github.com/moimart/gphotos-integration) (Home Assistant) stores "a snapshot of the photos you pick. To pick up newly added photos in an album, press the Re-pick photos button."
- [PyDevices](https://github.com/PyDevices/pydevices-examples/issues/145) uses the same pattern.

### Browser automation of your own session

These tools drive a logged-in Chromium and need no API:

- [perkeep/gphotos-cdp](https://github.com/perkeep/gphotos-cdp): 688 stars, last push 2024-06.
- [spraot/gphotos-cdp](https://github.com/spraot/gphotos-cdp): a fork, last push 2026-06.
- [Glassick](https://github.com/xeonforcecz/glassick): 0 stars. It "syncs a Google Photos album to a local cache once a night" and warns: "Browser automation of Google Photos is a grey area under Google's ToS. Use a dedicated Google account."
- rclone's `--gphotos-proxy` uses a headless browser too, but only for items rclone can already list.

This route delivers the exact refined goal. It needs an always-on machine (Chromium will not run on the Kindle), and it stores a full Google session cookie. Every Google Photos UI change can break it.

### Immich and ImmichFrame

- [ImmichFrame](https://immichframe.dev/docs/overview): "Immich is an excellent self-hosted media management solution – like your private Google Photos. But what if you want to display your favorite photos in a living room, hallway, or even on an e-ink display?"
- Immich has no live Google Photos sync. [immich-go](https://github.com/simulot/immich-go) imports Takeout archives: "It tries its best for importing google photos takeout archives."
- The live route is the Immich phone app's backup plus an Immich album. The Kindle's Go binary can poll the Immich album API with an API key. That album lives outside Google Photos.

### Google Data Portability API

Google's scope list has no Google Photos group. It covers chrome, discover, maps, myactivity, nest, play, youtube and others ([scopes](https://developers.google.com/identity/protocols/oauth2/scopes)). It is not a route.

### Phone-to-frame inbox (no Google)

Options include a Syncthing folder, a LAN upload page served by the frame, or a chat bot. MagicMirror users used MMM-TelegramBot, but Telegram sees the photos. These deliver "share to frame" with no Google involvement. Latency is seconds to minutes.

---

## 8. Comparison of viable routes

| Route | Setup effort | Owner's day-to-day effort | Privacy: what Google grants / what leaves Google | Failure risk | Update latency |
|---|---|---|---|---|---|
| **Drive folder + second account, `drive.readonly`** | Medium. Cloud project, Desktop client, publish as unverified, one laptop consent for the frame account, share one folder | Share to Drive folder from Google Photos (per batch) | The frame token reads the frame account's Drive, which holds only the shared folder; photos go Drive to Kindle | Low. Stable API; token dies only on revoke or 6 months idle; the warning screen appears only at setup | Poll interval (minutes) |
| **Picker API (QR on Kindle)** | Medium. Cloud project, Picker API, Desktop client, publish unverified, laptop consent | Scan the QR, search the album, select new photos, tap Done (per batch) | Narrowest grant: only the picked items; a copy lands on the Kindle | Low for the API; medium for UX, since session expiry (1-7 days, UNVERIFIED) and the 60-minute `baseUrl` force an immediate download | Whenever the owner picks |
| **Browser automation on a home server** | High. Always-on box, Chromium, dedicated Google account that receives a shared album, scraper upkeep | None. Add to the album as usual | A full Google session cookie sits on your server; ToS grey area | High. UI changes break it; Google may challenge the login | Poll interval |
| **Immich album** | High. Run Immich (Docker), phone app backup | Add to the Immich album (photos also still back up to Google Photos if wanted) | Nothing goes to Google for this path; fully self-hosted | Medium. You run the server | Seconds to minutes |
| **Ambient API** | n/a for an individual | None | Curated items from chosen albums | Blocked: partner-only | Up to 240 list calls per device per day |
| **Takeout scheduled** | Low | None | Full export of chosen data to Drive, Dropbox, OneDrive or Box | Low | Up to 2 months, and for 1 year only |

Routes that fail the goal are excluded: Library API app-created album, shared album with a second account, rclone, gphotos-sync.

---

## 9. Recommendation

1. **Primary: the private Drive folder** (section 6). Use a second "frame" Google account and share one folder with it as Viewer, with link access Restricted. The Kindle holds a `drive.readonly` refresh token for that account, from a Desktop OAuth client published as an unverified personal app (no 7-day expiry). The owner's habit changes from "Add to album" to "Share to Drive folder" in the Google Photos app. After that, the frame updates by itself and nothing uses link sharing. This comes closest to the refined goal with official APIs.
2. **Optional add-on: a Picker "pull from Google Photos" button.** The Kindle shows a QR code, the owner searches the album name and selects photos, and the frame saves copies at `=w1072-h1448`. Use it for occasional batches straight from the library. It grants the least access of any route, but it never updates by itself.
3. **Keep the local photo set** as the fallback. Show the cached Drive or Picker copies when offline or when a token fails.
4. **Do not build on** the Library API app-created album, shared albums, rclone or gphotos-sync. None of them can see photos you add in the Photos app.
5. **Watch the Ambient API.** If Google opens it to individuals, it delivers the exact goal: albums as live media sources and 240 list calls per device per day. A one-line interest-form submission costs nothing, but the form expects a company.
6. **Browser automation** delivers the exact goal today. Use it only if the owner accepts the ToS risk, runs a home server, and uses a dedicated Google account that receives the album through specific-person sharing. Never use it with the main account.

**Kindle implementation notes**

- Do a one-time consent on a laptop (loopback plus PKCE), then copy `client_id`, `client_secret` and `refresh_token` to the Kindle.
- Refresh the access token before each poll.
- Download bytes right after listing, with an `Authorization: Bearer` header, because Picker `baseUrl`s need it and expire in 60 minutes.
- Use the picked item `id` or the Drive `fileId` to skip duplicates.
- Run the grayscale conversion on the device.

---

## 10. UNVERIFIED items

- The Picker scope's classification (sensitive vs restricted). Only developer reports say sensitive; Google's docs say only that verification is required.
- Picker session lifetime (`expireTime`): reports say about 24 hours and about 7 days. Google publishes no value.
- Picker support for Android and iOS OAuth client types. Desktop and Web clients work per secondary sources.
- Whether the Picker offers "select all" on an album search result.
- The Kilian Lehn test (`mediaItemsCount: 12`, 0 items returned). I saw it only via a search-engine summary; the site was down (HTTP 521).
- Whether Google accepts an individual into the Ambient partner program; whether Ambient media sources include shared albums; whether Google allowlists `photosambient.mediaitems` per partner for the device flow.
- Whether `drive.file` sees files that a user adds to an app-created or Picker-selected folder. Probably no.
- That a `drive.readonly` token for a second account lists a folder shared with it. Standard Drive behavior, but not tested here.
- Exact Google Photos share-sheet labels for "Save to Drive" on Android and iOS, and whether the shared copy keeps the original quality.
- rclone's claim that publishing needs a homepage and privacy-policy URL even for a personal app.
- The contents of Google issue tracker 368779600, which I saw only as quoted on GitHub.
