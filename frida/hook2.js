/* Viddo 抓参钩子 v2：全量 OkHttp + AI 服务参数 + 响应 message */
Java.perform(function () {
  function log(s) { console.log(s); }

  // 抓所有 OkHttp 请求（不过滤域名）
  try {
    var RB = Java.use('okhttp3.Request$Builder');
    RB.build.implementation = function () {
      var req = this.build();
      try { log('[HTTP] ' + req.method() + ' ' + req.url().toString()); } catch (e) {}
      return req;
    };
    log('[hook] okhttp builder OK');
  } catch (e) { log('[hook] okhttp FAIL ' + e); }

  // 响应体（看服务端返回了什么）
  try {
    var RB2 = Java.use('okhttp3.ResponseBody');
    var Resp = Java.use('okhttp3.Response');
    log('[hook] okhttp response classes OK');
  } catch (e) {}

  // AI 服务：参数加密入口
  try {
    var d = Java.use('com.energysh.aiservice.api.d');
    var bOver = d.b.overload('java.lang.String', 'com.energysh.aiservice.api.AiFunAction', '[Lkotlin.Pair;');
    bOver.implementation = function (priority, action, pairs) {
      var out = [];
      try { for (var i = 0; i < pairs.length; i++) out.push(pairs[i].getFirst() + '=' + pairs[i].getSecond()); } catch (e) { out.push('ERR:' + e); }
      log('[D.B] priority=' + priority + ' action=' + action + ' extra={' + out.join(', ') + '}');
      return bOver.call(this, priority, action, pairs);
    };
    log('[hook] d.b OK');
  } catch (e) { log('[hook] d.b FAIL ' + e); }

  // AI 服务：任意 multipart 实现
  ['c0', 'd0', 'ImageToVideo3MultipartImpl', 'ImageToVideo4MultipartImpl', 'ImageToVideo5MultipartImpl',
   'TextToImage2MultipartImpl', 'TextToImageMultipartImpl', 'Image2ImageMultipartImpl',
   'EnhanceMultipartImpl', 'Enhance2MultipartImpl', 'Enhance3MultipartImpl'].forEach(function (cls) {
    try {
      var C = Java.use('com.energysh.aiservice.repository.multipart.energy.' + cls);
      C.b.overload('kotlin.coroutines.c').implementation = function (cont) {
        log('[MULTIPART] ' + cls + '.b()');
        return this.b(cont);
      };
      log('[hook] ' + cls + ' OK');
    } catch (e) {}
  });

  // AI 服务响应 bean（message/code）
  try {
    var Bean = Java.use('com.energysh.aiservice.bean.AIServiceBean');
    Bean.getMessage.implementation = function () {
      var m = this.getMessage();
      try { log('[BEAN] code=' + this.getCode() + ' message=' + m); } catch (e) {}
      return m;
    };
    log('[hook] AIServiceBean OK');
  } catch (e) { log('[hook] AIServiceBean FAIL ' + e); }

  // 积分入口
  try {
    var P = Java.use('com.energysh.points.api.EnjoyEncryptApi');
    P.h.overload('java.lang.String', 'java.util.Map', 'int', 'kotlin.coroutines.c').implementation = function (url, map, retry, c) {
      log('[POINTS] ' + url + ' map=' + map);
      return this.h(url, map, retry, c);
    };
    log('[hook] EnjoyEncryptApi.h OK');
  } catch (e) { log('[hook] points FAIL ' + e); }
});
