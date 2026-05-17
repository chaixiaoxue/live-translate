# webrtcvad-wheels exposes the module as "webrtcvad" but its distribution
# metadata is not named "webrtcvad", so the contrib hook fails while copying
# metadata. The extension module is discovered by normal analysis.
