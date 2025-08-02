package com.duong_21011224.scada;

import androidx.appcompat.app.AppCompatActivity;

import android.os.Bundle;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;
import android.util.Log;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

import java.io.IOException;

// Thêm import cho JSON
import org.json.JSONObject;
import org.json.JSONException;

// Thêm import cho Handler và Looper
import android.os.Handler;
import android.os.Looper;

public class MainActivity extends AppCompatActivity {

    private final String SERVER_URL = "http://192.168.137.1:5000";
    private static final String TAG = "SCADA_APP";

    // Khai báo các thành phần UI mới cho thang máy
    TextView tvCabinPositionDisplay;

    // Nút bên trong Cabin
    Button btnCabinFloor1, btnCabinFloor2, btnCabinFloor3, btnCabinFloor4;
    Button btnCabinOpenDoor, btnCabinCloseDoor;

    // Nút bên ngoài Cabin
    Button btnOutside_Floor1Up;
    Button btnOutside_Floor2Up, btnOutside_Floor2Down;
    Button btnOutside_Floor3Up, btnOutside_Floor3Down;
    Button btnOutside_Floor4Down;

    // Nút Cập nhật Vị trí mới (ĐÃ LOẠI BỎ)
    // Button btnUpdatePosition; // Đã loại bỏ khai báo

    OkHttpClient client = new OkHttpClient();

    // Khai báo Handler và Runnable cho việc cập nhật định kỳ
    private Handler handler = new Handler(Looper.getMainLooper());
    private Runnable updatePositionRunnable;
    private static final long UPDATE_INTERVAL_MS = 1000; // Cập nhật mỗi 1 giây (1000ms)

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // Gán ID cho các TextView và Button
        tvCabinPositionDisplay = findViewById(R.id.tvCabinPositionDisplay);

        // Gán ID cho các nút bên trong Cabin
        btnCabinFloor1 = findViewById(R.id.btnCabinFloor1);
        btnCabinFloor2 = findViewById(R.id.btnCabinFloor2);
        btnCabinFloor3 = findViewById(R.id.btnCabinFloor3);
        btnCabinFloor4 = findViewById(R.id.btnCabinFloor4);
        btnCabinOpenDoor = findViewById(R.id.btnCabinOpenDoor);
        btnCabinCloseDoor = findViewById(R.id.btnCabinCloseDoor);

        // Gán ID cho các nút bên ngoài Cabin
        btnOutside_Floor1Up = findViewById(R.id.btnOutside_Floor1Up);
        btnOutside_Floor2Up = findViewById(R.id.btnOutside_Floor2Up);
        btnOutside_Floor2Down = findViewById(R.id.btnOutside_Floor2Down);
        btnOutside_Floor3Up = findViewById(R.id.btnOutside_Floor3Up);
        btnOutside_Floor3Down = findViewById(R.id.btnOutside_Floor3Down);
        btnOutside_Floor4Down = findViewById(R.id.btnOutside_Floor4Down);

        // Gán ID cho nút Cập nhật Vị trí mới (ĐÃ LOẠI BỎ)
        // btnUpdatePosition = findViewById(R.id.btnUpdatePosition); // Đã loại bỏ gán ID

        // Bắt sự kiện click cho các nút bên trong Cabin
        btnCabinFloor1.setOnClickListener(v -> sendRequest("/elevator/cabin/call/1"));
        btnCabinFloor2.setOnClickListener(v -> sendRequest("/elevator/cabin/call/2"));
        btnCabinFloor3.setOnClickListener(v -> sendRequest("/elevator/cabin/call/3"));
        btnCabinFloor4.setOnClickListener(v -> sendRequest("/elevator/cabin/call/4"));
        btnCabinOpenDoor.setOnClickListener(v -> sendRequest("/elevator/door/open"));
        btnCabinCloseDoor.setOnClickListener(v -> sendRequest("/elevator/door/close"));

        // Bắt sự kiện click cho các nút bên ngoài Cabin
        btnOutside_Floor1Up.setOnClickListener(v -> sendRequest("/elevator/floor/1/up"));
        btnOutside_Floor2Up.setOnClickListener(v -> sendRequest("/elevator/floor/2/up"));
        btnOutside_Floor2Down.setOnClickListener(v -> sendRequest("/elevator/floor/2/down"));
        btnOutside_Floor3Up.setOnClickListener(v -> sendRequest("/elevator/floor/3/up"));
        btnOutside_Floor3Down.setOnClickListener(v -> sendRequest("/elevator/floor/3/down"));
        btnOutside_Floor4Down.setOnClickListener(v -> sendRequest("/elevator/floor/4/down"));

        // Bắt sự kiện click cho nút Cập nhật Vị trí thủ công (ĐÃ LOẠI BỎ)
        // if (btnUpdatePosition != null) {
        //     btnUpdatePosition.setOnClickListener(v -> sendRequest("/status"));
        // }

        // Khởi tạo Runnable để cập nhật vị trí
        updatePositionRunnable = new Runnable() {
            @Override
            public void run() {
                sendRequest("/status"); // Gửi yêu cầu lấy vị trí
                handler.postDelayed(this, UPDATE_INTERVAL_MS); // Lên lịch chạy lại sau UPDATE_INTERVAL_MS
            }
        };
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Bắt đầu cập nhật vị trí khi Activity hiển thị
        handler.post(updatePositionRunnable); // Chạy lần đầu ngay lập tức (hoặc sau một độ trễ nhỏ nếu muốn)
        Log.d(TAG, "Bắt đầu cập nhật vị trí định kỳ.");
    }

    @Override
    protected void onPause() {
        super.onPause();
        // Dừng cập nhật vị trí khi Activity bị ẩn
        handler.removeCallbacks(updatePositionRunnable);
        Log.d(TAG, "Dừng cập nhật vị trí định kỳ.");
    }

    private void sendRequest(String endpoint) {
        String fullUrl = SERVER_URL + endpoint;
        Log.d(TAG, "Đang gửi yêu cầu đến: " + fullUrl);

        Request request = new Request.Builder()
                .url(fullUrl)
                .build();

        client.newCall(request).enqueue(new Callback() {
            @Override
            public void onResponse(Call call, Response response) throws IOException {
                String res = response.body() != null ? response.body().string() : "Không có phản hồi";
                Log.d(TAG, "Nhận phản hồi từ server: " + res);

                runOnUiThread(() -> {
                    // Cập nhật TextView hiển thị vị trí cabin nếu endpoint là /status
                    if (endpoint.equals("/status") || endpoint.equals("/elevator/position")) {
                        try {
                            JSONObject jsonResponse = new JSONObject(res);
                            if (jsonResponse.has("display_text")) {
                                String displayText = jsonResponse.getString("display_text");
                                tvCabinPositionDisplay.setText("Cabin: " + displayText);
                            } else {
                                tvCabinPositionDisplay.setText("Cabin: Phản hồi không có 'display_text'");
                            }
                        } catch (JSONException e) {
                            Log.e(TAG, "Lỗi phân tích JSON vị trí cabin: " + e.getMessage());
                            tvCabinPositionDisplay.setText("Cabin: Lỗi JSON");
                        } catch (Exception e) {
                            Log.e(TAG, "Lỗi xử lý phản hồi vị trí cabin: " + e.getMessage());
                            tvCabinPositionDisplay.setText("Cabin: Lỗi dữ liệu");
                        }
                    } else {
                        //Toast.makeText(MainActivity.this, res, Toast.LENGTH_SHORT).show();
                    }
                });
            }

            @Override
            public void onFailure(Call call, IOException e) {
                e.printStackTrace();
                Log.e(TAG, "Lỗi kết nối server: " + e.getMessage());

                runOnUiThread(() -> {
                    String errorMessage = "❌ Lỗi kết nối: " + (e.getMessage() != null ? e.getMessage() : "Không xác định");
                    Toast.makeText(MainActivity.this, errorMessage, Toast.LENGTH_LONG).show();
                });
            }
        });
    }
}
