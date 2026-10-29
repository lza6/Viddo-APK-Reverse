/* 只为确认：AI SDK 初始化有没有跑、getUuid 有没有发 */
Java.perform(function () {
  function log(s) { console.log(s); }
  try {
    var L = Java.use('com.energysh.aiservice.AIServiceLib');
    L.h.implementation = function (ctx, appId, baseUrl, pk, ch, sky, z, cb) {
      log('[INIT] AIServiceLib.h appId=' + appId + ' baseUrl=' + baseUrl + ' channel=' + ch);
      return this.h(ctx, appId, baseUrl, pk, ch, sky, z, cb);
    };
    log('[hook] AIServiceLib.h OK');
  } catch (e) { log('[hook] AIServiceLib.h FAIL ' + e); }
  try {
    var S = Java.use('com.energysh.aiservice.api.ServiceApis');
    S.o.overload('kotlin.coroutines.c').implementation = function (c) {
      log('[INIT] updateServiceUUID() called');
      return this.o(c);
    };
    S.l.overload('java.lang.String').implementation = function (a) { var u = this.l(a); log('[URL] ' + u); return u; };
    log('[hook] ServiceApis OK');
  } catch (e) { log('[hook] ServiceApis FAIL ' + e); }
  try {
    var SDK = Java.use('com.energysh.quickart.server.ai.AIServiceSdk');
    SDK.a.overload('android.content.Context').implementation = function (ctx) {
      log('[INIT] AIServiceSdk.a() called from App.onCreate');
      return this.a(ctx);
    };
    log('[hook] AIServiceSdk OK');
  } catch (e) { log('[hook] AIServiceSdk FAIL ' + e); }
  try {
    var RB = Java.use('okhttp3.Request$Builder');
    RB.build.implementation = function () { var r = this.build(); try { log('[HTTP] ' + r.method() + ' ' + r.url().toString()); } catch (e) {} return r; };
    log('[hook] okhttp OK');
  } catch (e) {}
});
