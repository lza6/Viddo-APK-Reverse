/* Viddo 抓参钩子：dump AI 服务真实的 multipart 参数（platFormId/pointId/consumeType…） */
Java.perform(function () {
  function log(s) { console.log(s); }

  // 1) 参数加密入口：priority + extraData(Pair[])
  try {
    var d = Java.use('com.energysh.aiservice.api.d');
    var bOver = d.b.overload('java.lang.String', 'com.energysh.aiservice.api.AiFunAction', '[Lkotlin.Pair;');
    bOver.implementation = function (priority, action, pairs) {
      var out = [];
      try {
        for (var i = 0; i < pairs.length; i++) {
          out.push(pairs[i].getFirst() + '=' + pairs[i].getSecond());
        }
      } catch (e) { out.push('ERR:' + e); }
      log('[D.B] priority=' + priority + ' action=' + action + ' extra={' + out.join(', ') + '}');
      var r = bOver.call(this, priority, action, pairs);
      try { log('[D.B] -> content=' + r.getFirst() + ' sign=' + r.getSecond()); } catch (e2) {}
      return r;
    };
    log('[hook] d.b OK');
  } catch (e) { log('[hook] d.b FAIL ' + e); }

  // 2) URL 拼接：base + endpoint
  try {
    var sp = Java.use('com.energysh.aiservice.api.ServiceApis');
    sp.l.overload('java.lang.String').implementation = function (api) {
      var u = this.l(api);
      log('[URL] ' + u);
      return u;
    };
    log('[hook] ServiceApis.l OK');
  } catch (e) { log('[hook] ServiceApis.l FAIL ' + e); }

  // 3) 明文 content（multipart 里那个 paramsJson），在各 multipart 实现里统一拦
  ['c0', 'd0', 'ImageToVideo3MultipartImpl', 'ImageToVideo4MultipartImpl', 'ImageToVideo5MultipartImpl'].forEach(function (cls) {
    try {
      var C = Java.use('com.energysh.aiservice.repository.multipart.energy.' + cls);
      C.b.overload('kotlin.coroutines.c').implementation = function (cont) {
        log('[MULTIPART] ' + cls + ' called');
        return this.b(cont);
      };
      log('[hook] ' + cls + '.b OK');
    } catch (e) { log('[hook] ' + cls + ' FAIL ' + e); }
  });

  // 4) 积分：看 App 拿到的 pointId 与消耗选择
  try {
    var pts = Java.use('com.energysh.points.api.PointsApi');
    log('[hook] PointsApi found, methods=' + pts.class.getDeclaredMethods().length);
  } catch (e) { log('[hook] PointsApi FAIL ' + e); }

  // 5) 任何走 OkHttp 的请求 URL（兜底看完整链路）
  try {
    var R = Java.use('okhttp3.Request');
    var RB = Java.use('okhttp3.Request$Builder');
    RB.build.implementation = function () {
      var req = this.build();
      try {
        var u = req.url().toString();
        if (u.indexOf('magicutapp') >= 0 || u.indexOf('videoshowapp') >= 0) log('[HTTP] ' + req.method() + ' ' + u);
      } catch (e) {}
      return req;
    };
    log('[hook] okhttp Request.Builder OK');
  } catch (e) { log('[hook] okhttp FAIL ' + e); }
});
