package kr.moduyuga.app;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "KakaoShare")
public class KakaoSharePlugin extends Plugin {
    @PluginMethod
    public void share(PluginCall call) {
        String text = call.getString("text");
        if (text == null || text.trim().isEmpty() || text.length() > 3000) {
            call.reject("공유할 내용을 확인해 주세요.", "INVALID_TEXT");
            return;
        }
        getActivity().runOnUiThread(() -> {
            Intent intent = new Intent(Intent.ACTION_SEND);
            intent.setType("text/plain");
            intent.setPackage("com.kakao.talk");
            intent.putExtra(Intent.EXTRA_TEXT, text);
            try {
                getActivity().startActivity(intent);
                call.resolve();
            } catch (ActivityNotFoundException exception) {
                call.reject("카카오톡을 설치한 뒤 다시 시도해 주세요.", "KAKAO_NOT_INSTALLED");
            } catch (Exception exception) {
                call.reject("카카오톡 공유를 열지 못했습니다.", "SHARE_FAILED");
            }
        });
    }
}
