// 相机状态检查工具：报告 TCC 授权状态 + 设备列表 + 实际取流测试
// 用法: swiftc cam_status.swift -o cam_status && ./cam_status [request]
import AVFoundation
import Foundation

let args = CommandLine.arguments
let wantRequest = args.contains("request")

// 1) 授权状态
let status = AVCaptureDevice.authorizationStatus(for: .video)
print("TCC_RAW=\(status.rawValue)")
switch status {
case .authorized:
    print("TCC=authorized (已授权)")
case .notDetermined:
    print("TCC=notDetermined (从未询问过)")
case .denied:
    print("TCC=denied (被拒绝)")
case .restricted:
    print("TCC=restricted (受限制)")
@unknown default:
    print("TCC=unknown")
}

// 2) 设备列表
let devices = AVCaptureDevice.DiscoverySession(
    deviceTypes: [.builtInWideAngleCamera, .external, .continuityCamera],
    mediaType: .video,
    position: .unspecified
).devices
print("DEVICES=\(devices.count)")
for d in devices {
    print("  DEVICE: \(d.localizedName) | \(d.uniqueID)")
}

// 3) 未授权则尝试弹窗请求
if status == .notDetermined && wantRequest {
    print("REQUESTING... 请在屏幕上出现的弹窗点击「允许」(若 15 秒无弹窗则说明当前进程无法弹窗)")
    AVCaptureDevice.requestAccess(for: .video) { granted in
        print("REQUEST_RESULT=\(granted ? "granted" : "denied")")
        exit(0)
    }
    DispatchQueue.main.asyncAfter(deadline: .now() + 15) {
        print("REQUEST_RESULT=timeout (无 GUI 会话或弹窗被抑制)")
        exit(2)
    }
    RunLoop.main.run()
} else if status == .authorized {
    // 4) 实际取流测试
    guard let cam = devices.first else { print("CAPTURE=no-device"); exit(1) }
    do {
        let input = try AVCaptureDeviceInput(device: cam)
        let session = AVCaptureSession()
        session.addInput(input)
        let out = AVCaptureVideoDataOutput()
        session.addOutput(out)
        session.startRunning()
        Thread.sleep(forTimeInterval: 1.0)
        print("CAPTURE=\(session.isRunning ? "ok" : "fail")")
        session.stopRunning()
    } catch {
        print("CAPTURE=error: \(error)")
    }
}
exit(0)
